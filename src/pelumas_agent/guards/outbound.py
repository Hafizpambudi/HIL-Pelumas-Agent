import re
from dataclasses import dataclass, field

PRICE_FALLBACK = "Untuk harga, saya teruskan ke admin ya — sebentar."
STOCK_FALLBACK = "Saya cek dulu ketersediaannya ke gudang."
FITMENT_FALLBACK = "Perlu saya konfirmasi dulu kecocokannya dengan tim teknis."

PRICE_PATTERNS = [
    re.compile(r"\brp\s?[.,]?\s?\d", re.IGNORECASE),
    re.compile(r"\bidr\s?[.,]?\s?\d", re.IGNORECASE),
    re.compile(r"\bidr\b", re.IGNORECASE),
    re.compile(r"\b\d+[.,]?\d*\s*(juta|jt|ribu|rb|miliar|milyar)\b", re.IGNORECASE),
    re.compile(r"\b\d{1,3}(\.\d{3}){1,}\b"),
    re.compile(r"\b(usd|sgd|eur)\s?[.,]?\s?\d", re.IGNORECASE),
    re.compile(r"\b(harga|price)\b.{0,25}\b\d", re.IGNORECASE),
    re.compile(r"\b\d.{0,15}(per\s*(unit|pcs|buah|set))\b", re.IGNORECASE),
    re.compile(r"\b(diskon|potongan\s*hp?|potongan\s+harga|cashback)\b.{0,25}\d", re.IGNORECASE),
    re.compile(r"\b\d.{0,15}\s?(persen|%)\s*(diskon|potongan)", re.IGNORECASE),
    re.compile(r"\bnego\b", re.IGNORECASE),
    re.compile(r"\bharga\s+(net|netto|grosir|distributor)\b", re.IGNORECASE),
]

STOCK_PATTERNS = [
    re.compile(r"\bstok(nya)?\s+(tersedia|ready|ada|aman|banyak|cukup)\b", re.IGNORECASE),
    re.compile(r"\bready\s*(stock|stok)?\b", re.IGNORECASE),
    re.compile(r"\bbarang(nya)?\s+(ready|ada|tersedia)\b", re.IGNORECASE),
    re.compile(r"\bada\s+stok\b", re.IGNORECASE),
    re.compile(r"\btersedia\b", re.IGNORECASE),
    re.compile(r"\bstok\s+\d", re.IGNORECASE),
    re.compile(r"\b\d+\s*(pcs|unit|buah)\s+(ready|tersedia|di\s+stok)", re.IGNORECASE),
    re.compile(r"\bmasih\s+ada\b.{0,20}\b(stok|barang)\b", re.IGNORECASE),
]

FITMENT_PATTERNS = [
    re.compile(r"\bcocok\b", re.IGNORECASE),
    re.compile(r"\bpas\s+(untuk|dengan|di|buat)\b", re.IGNORECASE),
    re.compile(r"\bkompatibel\b", re.IGNORECASE),
    re.compile(r"\binterchangeable\b", re.IGNORECASE),
    re.compile(r"\bsetara\b", re.IGNORECASE),
    re.compile(r"\bidentik\b", re.IGNORECASE),
    re.compile(r"\bsama\s+persis\b", re.IGNORECASE),
    re.compile(r"\bbisa\s+dipakai\b", re.IGNORECASE),
    re.compile(r"\bbisa\s+masuk\b", re.IGNORECASE),
    re.compile(r"\bpengganti\s+(yang\s+)?(sama|identik|sepadan|langsung)\b", re.IGNORECASE),
    re.compile(r"\bdrop[- ]?in\b", re.IGNORECASE),
]


@dataclass
class GuardContext:
    admin_relay: bool = False
    stock_confirmed: bool = False
    fitment_backed: bool = False
    equivalence_backed: bool = False


@dataclass
class GuardOutcome:
    passed: bool
    blocks: list[str] = field(default_factory=list)
    fallback: str | None = None

    @property
    def final_text(self) -> str | None:
        return self.fallback


def check_price(text: str) -> str | None:
    for pattern in PRICE_PATTERNS:
        if pattern.search(text):
            return f"price:{pattern.pattern}"
    return None


def check_stock(text: str) -> str | None:
    for pattern in STOCK_PATTERNS:
        if pattern.search(text):
            return f"stock:{pattern.pattern}"
    return None


def check_fitment(text: str) -> str | None:
    for pattern in FITMENT_PATTERNS:
        if pattern.search(text):
            return f"fitment:{pattern.pattern}"
    return None


def run_guards(text: str, ctx: GuardContext | None = None) -> GuardOutcome:
    ctx = ctx or GuardContext()
    blocks: list[str] = []

    if not ctx.admin_relay:
        hit = check_price(text)
        if hit:
            blocks.append(hit)
            return GuardOutcome(False, blocks, PRICE_FALLBACK)

    if not ctx.stock_confirmed:
        hit = check_stock(text)
        if hit:
            blocks.append(hit)
            return GuardOutcome(False, blocks, STOCK_FALLBACK)

    if not (ctx.fitment_backed or ctx.equivalence_backed):
        hit = check_fitment(text)
        if hit:
            blocks.append(hit)
            return GuardOutcome(False, blocks, FITMENT_FALLBACK)

    return GuardOutcome(True, blocks, None)
