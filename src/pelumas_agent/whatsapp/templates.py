TEMPLATES = {
    "rfq_ack": {
        "name": "rfq_ack",
        "category": "UTILITY",
        "body": (
            "RFQ {{1}} sudah kami terima dan diteruskan ke admin. "
            "Kami kabari begitu ada harga."
        ),
    },
    "quote_ready": {
        "name": "quote_ready",
        "category": "UTILITY",
        "body": "Penawaran untuk {{1}} sudah siap dari admin kami. Terima kasih sudah menunggu.",
    },
    "need_info": {
        "name": "need_info",
        "category": "UTILITY",
        "body": "Untuk melanjutkan permintaan Anda, kami butuh info tambahan: {{1}}.",
    },
    "availability_pending": {
        "name": "availability_pending",
        "category": "UTILITY",
        "body": "Ketersediaan {{1}} sedang kami cek ke gudang. Kami kabari segera.",
    },
    "quote_eta": {
        "name": "quote_eta",
        "category": "UTILITY",
        "body": "{{1}}",
    },
}


def render(template_name: str, params: list[str]) -> str:
    body = TEMPLATES[template_name]["body"]
    for index, param in enumerate(params, start=1):
        body = body.replace("{{" + str(index) + "}}", param)
    return body
