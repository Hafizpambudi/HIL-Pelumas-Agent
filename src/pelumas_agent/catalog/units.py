import re

PSI_TO_BAR = 0.0689476
US_GALLON_L = 3.78541
IMP_GALLON_L = 4.54609
M3_PER_H_TO_LPM = 1000.0 / 60.0

_FRACTION_DIGITS = {
    "\u00bc": 0.25,
    "\u00bd": 0.5,
    "\u00be": 0.75,
    "\u2150": 0.125,
    "\u2151": 0.0625,
    "\u2152": 0.1875,
    "\u2153": 1 / 3,
    "\u2154": 2 / 3,
    "\u2155": 0.2,
    "\u2156": 0.4,
    "\u2157": 0.6,
    "\u2158": 0.8,
    "\u215b": 0.375,
    "\u215c": 0.625,
    "\u215d": 0.875,
}

_SIZE_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)?)?\s*(?:\s*(\d+)\s*/\s*(\d+))?\s*(?:[\u2033\"])?\s*"
    r"(?:inci|inch|in\.?)?\s*$",
    re.IGNORECASE,
)


def parse_size(raw: str | float | None) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = raw.strip()
    if not text:
        return None
    for glyph, value in _FRACTION_DIGITS.items():
        if glyph in text:
            head = text.split(glyph)[0].strip()
            whole = float(head) if head else 0.0
            return whole + value
    match = _SIZE_RE.match(text)
    if not match or (match.group(1) is None and match.group(2) is None):
        return None
    whole = float(match.group(1)) if match.group(1) else 0.0
    if match.group(2) and match.group(3):
        whole += float(match.group(2)) / float(match.group(3))
    return whole


def psi_to_bar(psi: float) -> float:
    return round(psi * PSI_TO_BAR, 4)


def f_to_c(f: float) -> float:
    return round((f - 32.0) * 5.0 / 9.0, 2)


def gpm_us_to_lpm(gpm: float) -> float:
    return round(gpm * US_GALLON_L, 2)


def gpm_imp_to_lpm(gpm: float) -> float:
    return round(gpm * IMP_GALLON_L, 2)


def m3h_to_lpm(m3h: float) -> float:
    return round(m3h * M3_PER_H_TO_LPM, 2)


def reconcile_flow(
    imp_gpm: float | None, lpm: float | None, m3h: float | None, tolerance: float = 0.05
) -> bool:
    candidates: list[float] = []
    if imp_gpm is not None:
        candidates.append(gpm_imp_to_lpm(imp_gpm))
    if lpm is not None:
        candidates.append(lpm)
    if m3h is not None:
        candidates.append(m3h_to_lpm(m3h))
    if len(candidates) < 2:
        return True
    base = candidates[0]
    if base <= 0:
        return False
    return all(abs(value - base) / base <= tolerance for value in candidates[1:])
