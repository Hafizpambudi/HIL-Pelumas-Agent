from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from pelumas_agent.availability.adapters import (
    ErpAdapter,
    ManualAdapter,
    SheetAdapter,
    get_adapter,
)
from pelumas_agent.availability.base import AvailabilityResult, check_availability
from pelumas_agent.config import get_settings
from pelumas_agent.db.models import AvailabilityCheck

__all__ = [
    "AvailabilityResult",
    "ErpAdapter",
    "ManualAdapter",
    "SheetAdapter",
    "check_availability",
    "get_adapter",
]


def freshness_ok(session: Session, part_no: str, state: str, source: str) -> bool:
    if state != "available" or source == "manual":
        return False
    window = timedelta(minutes=get_settings().availability_freshness_minutes)
    row = (
        session.execute(
            select(AvailabilityCheck)
            .where(AvailabilityCheck.part_no == part_no)
            .order_by(AvailabilityCheck.observed_at.desc())
        )
        .scalars()
        .first()
    )
    if row is None or row.observed_at is None:
        return False
    from pelumas_agent.db.models import utcnow

    return (utcnow() - row.observed_at) <= window
