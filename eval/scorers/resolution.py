import re

PART_TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,}[- ]?\d+[A-Z0-9]*\b")
ID_PREFIXES = ("RFQ", "WAMID", "HTTP", "HTTPS")


def normalize_part(token: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", token.upper())


def extract_parts_from_tool_results(tool_calls: list[dict]) -> set[str]:
    found: set[str] = set()
    for call in tool_calls:
        result = call.get("result") or {}
        products = result.get("products") or []
        if isinstance(products, list):
            for product in products:
                if isinstance(product, dict) and product.get("part_no"):
                    found.add(product["part_no"])
    return found


def score(case: dict, records: dict) -> dict:
    expected = case.get("expected", {}).get("resolution")
    resolved = records["resolved_parts"]

    if expected == "unresolved" or (expected is None and case.get("expect_unresolved")):
        passed = len(resolved) == 0
        return {
            "scorer": "resolution",
            "passed": passed,
            "detail": f"resolved={sorted(resolved)} expected=unresolved",
        }

    if not expected:
        return {"scorer": "resolution", "passed": True, "detail": "no expectation"}

    expected_set = {str(part) for part in expected}
    missing = expected_set - resolved
    return {
        "scorer": "resolution",
        "passed": not missing,
        "detail": f"expected={sorted(expected_set)} resolved={sorted(resolved)}",
    }
