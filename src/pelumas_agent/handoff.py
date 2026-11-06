from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from pelumas_agent.config import Settings
from pelumas_agent.db.models import Conversation, Event, Rfq
from pelumas_agent.whatsapp.session_window import in_window
from pelumas_agent.whatsapp.templates import render

PENDING_STAGES = {"HANDOFF", "AWAIT_PRICE"}
MAX_ETA_NOTICES = 1


def _state_cls():
    from pelumas_agent.orchestrator.state import ConversationState

    return ConversationState


def format_eta(minutes: int) -> str:
    if minutes <= 0:
        return "beberapa menit"
    if minutes % 60 == 0:
        hours = minutes // 60
        return "1 jam" if hours == 1 else f"{hours} jam"
    return f"{minutes} menit"


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def is_overdue(state, settings: Settings, now: datetime | None = None) -> bool:
    if state.stage not in PENDING_STAGES:
        return False
    if state.eta_notice_count >= MAX_ETA_NOTICES:
        return False
    handoff_at = _parse(state.handoff_at)
    if handoff_at is None:
        return False
    now = now or datetime.now(timezone.utc)
    return now - handoff_at >= timedelta(minutes=settings.handoff_eta_minutes)


def buyer_notice(rfq_id: str) -> str:
    return (
        f"Update untuk {rfq_id}: admin kami belum membalas. "
        "Permintaan Anda masih di antrean dan tidak hilang. "
        "Saya kabari lagi begitu ada harga."
    )


def admin_nudge(rfq_id: str, overdue_minutes: int) -> str:
    return (
        f"Reminder: {rfq_id} belum dibalas, sudah {format_eta(overdue_minutes)}. "
        "Pembeli sudah kami beri tahu."
    )


def _send_buyer(conversation: Conversation, text: str, transport, use_template: bool) -> str:
    if transport is None:
        return text
    if not use_template:
        transport.send(conversation.buyer_phone, text)
    elif hasattr(transport, "send_template"):
        transport.send_template(conversation.buyer_phone, "quote_eta", [{"text": text}])
    else:
        transport.send(conversation.buyer_phone, render("quote_eta", [text]))
    return text


def pending_eta_notice(
    session: Session,
    conversation: Conversation,
    settings: Settings,
    transport=None,
    now: datetime | None = None,
) -> str | None:
    if conversation.paused:
        return None
    state = _state_cls().from_dict(conversation.state_json)
    if not is_overdue(state, settings, now):
        return None
    if not state.rfq_id:
        return None

    handoff_at = _parse(state.handoff_at)
    reference = now or datetime.now(timezone.utc)
    overdue_minutes = int((reference - handoff_at).total_seconds() // 60) if handoff_at else 0

    use_template = not in_window(conversation, now=now)

    state.eta_notice_count += 1
    conversation.state_json = state.to_dict()
    session.commit()

    notice = _send_buyer(conversation, buyer_notice(state.rfq_id), transport, use_template)
    if transport is not None:
        for admin in settings.admin_numbers:
            transport.send(admin, admin_nudge(state.rfq_id, overdue_minutes))

    session.add(
        Event(
            conversation_id=conversation.id,
            type="handoff_pending",
            payload={
                "rfq_id": state.rfq_id,
                "overdue_minutes": overdue_minutes,
                "notice_count": state.eta_notice_count,
            },
        )
    )
    session.commit()
    return notice


def sweep_pending_handoffs(
    session: Session,
    settings: Settings,
    transport=None,
    now: datetime | None = None,
    dry_run: bool = False,
) -> list[dict]:
    rows = (
        session.execute(select(Conversation).where(Conversation.paused.is_(False)))
        .scalars()
        .all()
    )
    results: list[dict] = []
    for conversation in rows:
        state = _state_cls().from_dict(conversation.state_json)
        if not is_overdue(state, settings, now):
            continue
        entry = {
            "conversation_id": conversation.id,
            "buyer_phone": conversation.buyer_phone,
            "rfq_id": state.rfq_id,
            "stage": state.stage,
        }
        if not dry_run:
            pending_eta_notice(session, conversation, settings, transport, now)
            entry["notified"] = True
        results.append(entry)
    return results


def mark_handoff_sent(
    session: Session, conversation: Conversation, rfq_id: str, now: datetime | None = None
) -> None:
    state = _state_cls().from_dict(conversation.state_json)
    state.handoff_at = (now or datetime.now(timezone.utc)).isoformat()
    state.eta_notice_count = 0
    conversation.state_json = state.to_dict()
    rfq = session.get(Rfq, rfq_id)
    if rfq is not None and rfq.status == "ready":
        rfq.status = "sent_to_admin"
    session.commit()


def clear_notices(conversation: Conversation) -> None:
    state = _state_cls().from_dict(conversation.state_json)
    state.eta_notice_count = 0
    state.handoff_at = None
    conversation.state_json = state.to_dict()


