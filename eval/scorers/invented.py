from eval.scorers.resolution import ID_PREFIXES, PART_TOKEN_RE, normalize_part


def score(case: dict, records: dict) -> dict:
    known = records["known_parts"]
    violations = []
    for reply in records["replies"]:
        for token in PART_TOKEN_RE.findall(reply):
            if token.upper().startswith(ID_PREFIXES):
                continue
            candidate = normalize_part(token)
            if candidate and candidate not in known:
                violations.append(token)
    return {
        "scorer": "invented",
        "passed": not violations,
        "detail": f"invented={violations}" if violations else "clean",
    }
