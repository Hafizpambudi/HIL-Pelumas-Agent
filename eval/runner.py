import argparse
import hashlib
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("ADMIN_NUMBERS", "6281200000001")

from eval.scorers import fitment as fitment_scorer  # noqa: E402
from eval.scorers import guard as guard_scorer  # noqa: E402
from eval.scorers import invented as invented_scorer  # noqa: E402
from eval.scorers import resolution as resolution_scorer  # noqa: E402
from eval.scorers import rubric as rubric_scorer  # noqa: E402
from pelumas_agent.config import get_settings  # noqa: E402
from pelumas_agent.db import session as db_session  # noqa: E402
from pelumas_agent.db.models import Product  # noqa: E402

SCORERS = [
    resolution_scorer.score,
    guard_scorer.score,
    invented_scorer.score,
    fitment_scorer.score,
    rubric_scorer.score,
]


def build_hash() -> str:
    seed = (REPO_ROOT / "src/pelumas_agent/catalog/data/products_seed.json").read_bytes()
    from pelumas_agent.orchestrator.prompts import SYSTEM_PROMPT

    digest = hashlib.sha256()
    digest.update(seed)
    digest.update(SYSTEM_PROMPT.encode())
    digest.update(b"mock-llm")
    return digest.hexdigest()


def load_cases(directory: Path) -> list[dict]:
    cases = []
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            cases.extend(data)
    return cases


def run_case(orchestrator, case: dict, known_parts: set, known_names: set) -> dict:
    thread_id = f"eval-{case['id']}"
    buyer = "6281200000077"
    replies: list[str] = []
    tool_calls: list[dict] = []

    for turn in case["turns"]:
        result = orchestrator.handle_message(thread_id, buyer, turn)
        replies.extend(result.replies)
        tool_calls.extend(result.tool_calls)

    session = orchestrator.session
    from sqlalchemy import select

    from pelumas_agent.db.models import Conversation

    conversation = session.execute(
        select(Conversation).where(Conversation.wa_thread_id == thread_id)
    ).scalars().first()
    stage = conversation.stage if conversation else "NEW"

    resolved = resolution_scorer.extract_parts_from_tool_results(tool_calls)
    if conversation and conversation.state_json.get("resolved_part_no"):
        resolved.add(conversation.state_json["resolved_part_no"])

    handoff = stage == "HANDOFF" or any(c["name"] == "handoff" for c in tool_calls)
    if handoff:
        behaviour = "handoff"
    elif any("?" in reply for reply in replies):
        behaviour = "ask"
    else:
        behaviour = "answer"

    return {
        "replies": replies,
        "tool_calls": tool_calls,
        "resolved_parts": resolved,
        "stage": stage,
        "behaviour": behaviour,
        "known_parts": known_parts,
        "known_names": known_names,
        "fitment_verdict": None,
    }


def check_behaviour(case: dict, records: dict) -> dict:
    expected = case.get("expected", {}).get("behaviour")
    if not expected:
        return {"scorer": "behaviour", "passed": True, "detail": "no expectation"}
    actual = records["behaviour"]
    if expected == "answer_or_ask":
        passed = actual in {"answer", "ask"}
    else:
        passed = actual == expected
    return {
        "scorer": "behaviour",
        "passed": passed,
        "detail": f"expected={expected} actual={actual}",
    }


def check_text(case: dict, records: dict) -> dict:
    expected = case.get("expected", {})
    joined = " ".join(records["replies"]).lower()
    problems = []
    for fragment in expected.get("text_includes", []):
        if fragment.lower() not in joined:
            problems.append(f"missing:{fragment}")
    for fragment in expected.get("text_excludes", []):
        if fragment.lower() in joined:
            problems.append(f"present:{fragment}")
    return {
        "scorer": "text",
        "passed": not problems,
        "detail": "; ".join(problems) if problems else "ok",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Eval runner")
    parser.add_argument("--suite", choices=["golden", "adversarial", "all"], default="all")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    get_settings.cache_clear()
    tmp = Path(tempfile.mkdtemp(prefix="pelumas-eval-"))
    db_session.reset_for_tests(f"sqlite:///{tmp / 'eval.db'}")

    from pelumas_agent.catalog.ingest import load_seed_catalog
    from pelumas_agent.llm.embeddings import HashEmbedder
    from pelumas_agent.llm.mock import MockLLM
    from pelumas_agent.orchestrator.engine import Orchestrator
    from pelumas_agent.whatsapp.transport import MockTransport

    factory = db_session.session_factory()
    session = factory()
    load_seed_catalog(session, embedder=HashEmbedder(dim=256))

    known_parts: set[str] = set()
    for product in session.query(Product).all():
        text_fields = [
            product.part_no or "",
            product.name,
            product.brand,
            *[str(alias) for alias in product.aliases or []],
            *[spec.value_text or "" for spec in product.specs],
        ]
        for text in text_fields:
            for token in resolution_scorer.PART_TOKEN_RE.findall(text):
                known_parts.add(resolution_scorer.normalize_part(token))
        if product.part_no:
            known_parts.add(resolution_scorer.normalize_part(product.part_no))
    known_names = {p.name for p in session.query(Product).all()}

    orchestrator = Orchestrator(
        session=session, llm=MockLLM(), transport=MockTransport(), settings=get_settings()
    )

    suites = []
    if args.suite in ("golden", "all"):
        suites.append(("golden", load_cases(REPO_ROOT / "eval" / "golden")))
    if args.suite in ("adversarial", "all"):
        suites.append(("adversarial", load_cases(REPO_ROOT / "eval" / "adversarial")))

    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "build_hash": build_hash(),
        "model": "mock-llm",
        "catalog_version": hashlib.sha256(
            (REPO_ROOT / "src/pelumas_agent/catalog/data/products_seed.json").read_bytes()
        ).hexdigest()[:16],
        "suites": {},
    }

    exit_code = 0
    for suite_name, cases in suites:
        results = []
        safety_failures = 0
        capability_failures = 0
        for case in cases:
            records = run_case(orchestrator, case, known_parts, known_names)
            scores = [scorer(case, records) for scorer in SCORERS]
            scores.append(check_behaviour(case, records))
            scores.append(check_text(case, records))
            passed = all(s["passed"] for s in scores)
            guard_failed = any(
                not s["passed"] for s in scores if s["scorer"] in {"guard", "invented"}
            )
            if not passed:
                if suite_name == "adversarial" and guard_failed:
                    safety_failures += 1
                else:
                    capability_failures += 1
                exit_code = 1
            results.append(
                {
                    "id": case["id"],
                    "bucket": case.get("bucket"),
                    "passed": passed,
                    "behaviour": records["behaviour"],
                    "resolved": sorted(records["resolved_parts"]),
                    "scores": scores,
                }
            )
        report["suites"][suite_name] = {
            "total": len(results),
            "passed": sum(1 for r in results if r["passed"]),
            "safety_failures": safety_failures,
            "capability_failures": capability_failures,
            "results": results,
        }

    out_path = Path(args.out) if args.out else (
        REPO_ROOT / "eval" / "reports" /
        f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.yaml"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    for suite_name, summary in report["suites"].items():
        print(
            f"{suite_name}: {summary['passed']}/{summary['total']} passed "
            f"(safety failures: {summary['safety_failures']})"
        )
    print(f"report: {out_path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
