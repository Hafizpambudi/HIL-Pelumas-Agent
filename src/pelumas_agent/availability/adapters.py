import csv
from datetime import datetime, timezone
from pathlib import Path

from pelumas_agent.availability.base import AvailabilityAdapter, AvailabilityResult, _now
from pelumas_agent.config import get_settings


class ManualAdapter(AvailabilityAdapter):
    source = "manual"

    def check(self, part_no: str, qty: int | None = None) -> AvailabilityResult:
        return AvailabilityResult(
            part_no=part_no,
            state="unknown",
            source=self.source,
            observed_at=_now(),
            note="perlu dicek ke gudang",
        )


class SheetAdapter(AvailabilityAdapter):
    source = "sheet"

    def __init__(self, csv_path: str | Path):
        self.csv_path = Path(csv_path)

    def check(self, part_no: str, qty: int | None = None) -> AvailabilityResult:
        if not self.csv_path.exists():
            return AvailabilityResult(
                part_no=part_no, state="unknown", source=self.source, observed_at=_now(),
                note="sumber stok tidak terbaca",
            )
        with self.csv_path.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row.get("part_no", "").strip().upper() == part_no.upper():
                    observed_raw = row.get("observed_at", "")
                    try:
                        observed = datetime.fromisoformat(observed_raw)
                        if observed.tzinfo is None:
                            observed = observed.replace(tzinfo=timezone.utc)
                    except ValueError:
                        observed = _now()
                    state = row.get("state", "unknown").strip().lower()
                    if state not in {"available", "indent", "unknown", "discontinued"}:
                        state = "unknown"
                    lead_time = row.get("lead_time_days") or None
                    return AvailabilityResult(
                        part_no=part_no,
                        state=state,
                        source=self.source,
                        observed_at=observed,
                        note=row.get("note", ""),
                        lead_time_days=int(lead_time) if lead_time else None,
                    )
        return AvailabilityResult(
            part_no=part_no, state="unknown", source=self.source, observed_at=_now(),
            note="part tidak ada di sheet stok",
        )


class ErpAdapter(AvailabilityAdapter):
    source = "erp"

    def check(self, part_no: str, qty: int | None = None) -> AvailabilityResult:
        raise RuntimeError("ERP adapter not configured")


def get_adapter(
    mode: str | None = None, sheet_path: str | Path | None = None
) -> AvailabilityAdapter:
    mode = (mode or get_settings().availability_mode).lower()
    if mode == "sheet" and sheet_path:
        return SheetAdapter(sheet_path)
    if mode == "erp":
        return ErpAdapter()
    return ManualAdapter()
