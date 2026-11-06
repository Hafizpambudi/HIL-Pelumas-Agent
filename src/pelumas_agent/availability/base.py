from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class AvailabilityResult:
    part_no: str
    state: str
    source: str
    observed_at: datetime
    note: str = ""
    lead_time_days: int | None = None


class AvailabilityAdapter:
    source = "base"

    def check(self, part_no: str, qty: int | None = None) -> AvailabilityResult:
        raise NotImplementedError


def _now():
    return datetime.now(timezone.utc)


def check_availability(
    session, adapter, part_no: str, qty: int | None = None
) -> AvailabilityResult:
    from pelumas_agent.availability import freshness_ok
    from pelumas_agent.db.models import AvailabilityCheck, Product

    product = (
        session.query(Product).filter(Product.part_no == part_no).first()
    )
    if product is not None and product.status == "discontinued":
        result = AvailabilityResult(
            part_no=part_no,
            state="discontinued",
            source="product_status",
            observed_at=_now(),
            note="produk tidak diproduksi lagi",
        )
        session.add(
            AvailabilityCheck(
                part_no=part_no, state=result.state, source=result.source,
                qty=qty, observed_at=result.observed_at,
            )
        )
        session.commit()
        return result

    try:
        result = adapter.check(part_no, qty)
    except Exception:
        result = AvailabilityResult(
            part_no=part_no,
            state="unknown",
            source=getattr(adapter, "source", "unknown"),
            observed_at=_now(),
            note="sumber stok tidak dapat dihubungi",
        )

    is_stale = not freshness_ok(session, part_no, result.state, result.source)
    if result.state == "available" and is_stale:
        result = AvailabilityResult(
            part_no=part_no,
            state="unknown",
            source=result.source,
            observed_at=result.observed_at,
            note="data stok tidak cukup baru, perlu dicek ulang",
        )

    session.add(
        AvailabilityCheck(
            part_no=part_no, state=result.state, source=result.source,
            qty=qty, observed_at=result.observed_at,
        )
    )
    session.commit()
    return result
