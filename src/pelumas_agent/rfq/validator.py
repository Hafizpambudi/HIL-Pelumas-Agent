REQUIRED_FIELDS = ("items", "quantity", "delivery_city")

ITEM_KEYS = ("part_no", "name", "qty")


def validate_rfq_payload(payload: dict) -> tuple[bool, list[str]]:
    missing: list[str] = []

    items = payload.get("items") or []
    if not items:
        missing.append("items")
    else:
        for item in items:
            if not (item.get("part_no") or item.get("name")):
                missing.append("items.resolvable")
                break

    if not any(
        isinstance(item.get("qty"), int) and item.get("qty", 0) > 0 for item in items
    ):
        missing.append("quantity")

    city = payload.get("delivery_city")
    if not city or not str(city).strip():
        missing.append("delivery_city")

    return (len(missing) == 0, missing)


def missing_field_message(missing: list[str]) -> str:
    labels = {
        "items": "barang yang diminta (part/model)",
        "items.resolvable": "barang yang diminta (part/model)",
        "quantity": "jumlah (qty)",
        "delivery_city": "kota pengiriman",
    }
    parts = []
    for field in missing:
        label = labels.get(field)
        if label and label not in parts:
            parts.append(label)
    joined = ", ".join(parts)
    return (
        "Supaya bisa saya buatkan RFQ lengkap untuk admin, "
        f"mohon info: {joined}. Satu pesan saja cukup."
    )
