from collections import Counter
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from pelumas_agent.db.models import Conversation, Event, Rfq, utcnow


def weekly_report(session: Session, days: int = 7) -> dict:
    since = utcnow() - timedelta(days=days)

    conversations = (
        session.execute(
            select(Conversation).where(Conversation.created_at >= since)
        )
        .scalars()
        .all()
    )
    rfqs = (
        session.execute(select(Rfq).where(Rfq.created_at >= since)).scalars().all()
    )
    events = (
        session.execute(select(Event).where(Event.at >= since)).scalars().all()
    )

    guard_blocks = [e for e in events if e.type == "guard_block"]
    handoffs = [e for e in events if e.type == "handoff"]
    handoff_reasons = Counter(
        (e.payload or {}).get("reason", "unknown") for e in handoffs
    )

    part_counter: Counter = Counter()
    for rfq in rfqs:
        for item in rfq.items or []:
            key = item.get("part_no") or item.get("name") or "unknown"
            part_counter[key] += item.get("qty") or 1

    priced = [r for r in rfqs if r.status == "priced"]
    conversation_ids = {c.id for c in conversations}
    rfq_conversation_ids = {
        r.conversation_id for r in rfqs if r.conversation_id in conversation_ids
    }

    return {
        "window_days": days,
        "conversations": len(conversations),
        "rfqs": len(rfqs),
        "rfqs_priced": len(priced),
        "conversion": (len(rfq_conversation_ids) / len(conversations)) if conversations else 0.0,
        "top_requested_parts": part_counter.most_common(10),
        "guard_blocks": len(guard_blocks),
        "handoffs": len(handoffs),
        "handoff_reasons": dict(handoff_reasons),
    }
