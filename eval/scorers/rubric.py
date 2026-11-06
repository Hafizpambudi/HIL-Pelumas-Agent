import os


def score(case: dict, records: dict) -> dict:
    if not os.environ.get("OPENAI_API_KEY"):
        return {"scorer": "rubric", "passed": True, "detail": "skipped (no OPENAI_API_KEY)"}
    return {
        "scorer": "rubric",
        "passed": True,
        "detail": "skipped (v1: deterministic scorers gate)",
    }
