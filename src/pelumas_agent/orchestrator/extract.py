import re

CITIES = [
    "jakarta", "tangerang", "bekasi", "depok", "bogor", "serang", "cilegon",
    "bandung", "cirebon", "semarang", "surabaya", "malang", "yogyakarta",
    "solo", "medan", "palembang", "pekanbaru", "batam", "jambi", "lampung",
    "bandar lampung", "banjarmasin", "pontianak", "balikpapan", "samarinda",
    "makassar", "manado", "denpasar", "mataram", "kupang", "jayapura",
    "padang", "bengkulu", "aceh", "banda aceh",
]

QTY_RE = re.compile(r"\b(\d+)\s*(pcs|pc|unit|buah|set|ea|meter|m)\b", re.IGNORECASE)

PRICE_RE = re.compile(
    r"\b(harga|berapa|harganya|penawaran|quotation|quote|pricelist|price list|invoice|npwp)\b",
    re.IGNORECASE,
)

NEGOTIATION_RE = re.compile(
    r"\b(diskon|nego|kurangi|kurangin|potongan|cashback|lebih murah)\b", re.IGNORECASE
)

AVAILABILITY_RE = re.compile(
    r"\b(ready|stok(nya)?|stock|tersedia|ada\s+barang|ketersediaan|indent)\b", re.IGNORECASE
)

SUBSTITUTION_RE = re.compile(
    r"(pengganti|alternatif|substitusi|ekuivalen|equivalent|kalau\b.+\b(kosong|habis|ga\s+ada|nggak\s+ada)|jika\b.+\b(kosong|habis))",
    re.IGNORECASE,
)

COMPARISON_RE = re.compile(
    r"\b(bedanya|perbedaan|bandingkan|banding|compare|vs|versus)\b", re.IGNORECASE
)

BOT_RE = re.compile(
    r"\b(kamu\s+(bot|robot|ai)|apakah\s+(kamu|ini)\s+(bot|robot|ai))\b", re.IGNORECASE
)

INJECTION_RE = re.compile(
    r"(abaikan\s+(semua\s+)?instruksi|ignore\s+(all\s+)?(previous|prior)|lupakan\s+(aturan|instruksi)|system\s*prompt)",
    re.IGNORECASE,
)

URGENCY_WORDS = re.compile(
    r"\b(urgent|segera|asap|butuh\s+cepat|hari\s+ini|besok|cepat|penting|mendesak)\b",
    re.IGNORECASE,
)

FLUID_WORDS = {
    "solar": "diesel",
    "diesel": "diesel",
    "biosolar": "diesel",
    "bensin": "petrol",
    "pertalite": "petrol",
    "pertamax": "petrol",
    "premium": "petrol",
    "avtur": "jet a1",
    "jet a1": "jet a1",
    "avgas": "avgas",
    "air": "water",
    "lpg": "lpg",
    "gas": "lpg",
    "oli": "lubricant",
    "pelumas": "lubricant",
    "solvent": "solvent",
}

INCH_RE = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*(?:\"|\u2033|inci|inch|in)\b", re.IGNORECASE)
BAR_RE = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*bar\b", re.IGNORECASE)
PSI_RE = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*psi\b", re.IGNORECASE)
FLOW_RE = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(lpm|l/m|liter\s*/?\s*menit|liter\s*per\s*menit)\b",
    re.IGNORECASE,
)


def extract_qty(text: str) -> int | None:
    match = QTY_RE.search(text)
    if match:
        return int(match.group(1))
    return None


def extract_city(text: str) -> str | None:
    lowered = text.lower()
    for city in CITIES:
        if city in lowered:
            return city.title()
    return None


def extract_fluid(text: str) -> str | None:
    lowered = text.lower()
    for word, canonical in FLUID_WORDS.items():
        if word in lowered:
            return canonical
    return None


def extract_connection_size(text: str) -> float | None:
    match = INCH_RE.search(text)
    if match:
        try:
            return float(match.group(1).replace(",", "."))
        except ValueError:
            return None
    return None


def extract_pressure_bar(text: str) -> float | None:
    match = BAR_RE.search(text)
    if match:
        return float(match.group(1).replace(",", "."))
    match = PSI_RE.search(text)
    if match:
        from pelumas_agent.catalog.units import psi_to_bar

        return psi_to_bar(float(match.group(1).replace(",", ".")))
    return None


def extract_flow_lpm(text: str) -> float | None:
    match = FLOW_RE.search(text)
    if match:
        return float(match.group(1).replace(",", "."))
    return None


def detect_intent(text: str) -> dict:
    return {
        "price": bool(PRICE_RE.search(text)),
        "negotiation": bool(NEGOTIATION_RE.search(text)),
        "availability": bool(AVAILABILITY_RE.search(text)),
        "substitution": bool(SUBSTITUTION_RE.search(text)),
        "comparison": bool(COMPARISON_RE.search(text)),
        "bot_question": bool(BOT_RE.search(text)),
        "injection": bool(INJECTION_RE.search(text)),
        "urgency": bool(URGENCY_WORDS.search(text)),
    }


def detect_language(text: str) -> str:
    english_markers = re.findall(
        r"\b(what|which|price|please|need|want|delivery|quote|the|for|with)\b",
        text.lower(),
    )
    if len(english_markers) >= 2:
        return "en"
    return "id"


PRICE_AMOUNT_RE = re.compile(
    r"(rp\s?[.,]?\s?\d[\d.,]*|\b\d[\d.,]*\s?(juta|jt|ribu|rb|miliar)\b|\b\d{1,3}(\.\d{3}){1,}\b)",
    re.IGNORECASE,
)


def extract_price_amount(text: str) -> str | None:
    match = PRICE_AMOUNT_RE.search(text)
    if match:
        return match.group(0).strip()
    return None
