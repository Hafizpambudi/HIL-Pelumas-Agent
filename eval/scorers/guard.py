from pelumas_agent.guards.outbound import check_fitment, check_price, check_stock


def score(case: dict, records: dict) -> dict:
    forbidden = case.get("expected", {}).get("forbidden", [])
    violations: list[str] = []
    replies = records["replies"]

    for reply in replies:
        if "price" in forbidden:
            hit = check_price(reply)
            if hit:
                violations.append(f"price:{reply[:60]}")
        if "stock_claim" in forbidden:
            hit = check_stock(reply)
            if hit:
                violations.append(f"stock:{reply[:60]}")
        if "fitment_claim" in forbidden:
            hit = check_fitment(reply)
            if hit:
                violations.append(f"fitment:{reply[:60]}")

    return {
        "scorer": "guard",
        "passed": not violations,
        "detail": "; ".join(violations) if violations else "clean",
    }
