def score(case: dict, records: dict) -> dict:
    expected = case.get("expected", {}).get("fitment")
    if not expected:
        return {"scorer": "fitment", "passed": True, "detail": "not applicable"}

    claimed = records.get("fitment_verdict")
    dimension = expected.get("dimension")
    wanted = expected.get("verdict")

    if claimed is None:
        passed = wanted == "none"
        return {
            "scorer": "fitment",
            "passed": passed,
            "detail": f"no fitment claim made, expected={wanted}",
        }

    passed = claimed.get("verdict") == wanted
    if dimension and claimed.get("dimension") not in (dimension, None):
        passed = passed and claimed.get("dimension") == dimension
    return {
        "scorer": "fitment",
        "passed": passed,
        "detail": f"claimed={claimed} expected={expected}",
    }
