from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from pelumas_agent.config import get_settings
from pelumas_agent.db.models import Conversation, Event, Rfq
from pelumas_agent.handoff import (
    buyer_notice,
    format_eta,
    is_overdue,
    mark_handoff_sent,
    pending_eta_notice,
    sweep_pending_handoffs,
)
from pelumas_agent.llm.mock import MockLLM
from pelumas_agent.orchestrator.engine import Orchestrator
from pelumas_agent.orchestrator.state import ConversationState
from pelumas_agent.whatsapp.transport import MockTransport

BUYER = "6281200000099"
ADMIN = "6281200000001"


def test_format_eta():
    assert format_eta(60) == "1 jam"
    assert format_eta(120) == "2 jam"
    assert format_eta(45) == "45 menit"
    assert format_eta(0) == "beberapa menit"


def _state(**overrides):
    state = ConversationState(stage="AWAIT_PRICE", rfq_id="RFQ-2026-11-0001")
    for key, value in overrides.items():
        setattr(state, key, value)
    return state


def test_not_overdue_before_threshold():
    settings = get_settings()
    state = _state(handoff_at=datetime.now(timezone.utc).isoformat())
    assert not is_overdue(state, settings)


def test_overdue_after_threshold():
    settings = get_settings()
    past = datetime.now(timezone.utc) - timedelta(minutes=settings.handoff_eta_minutes + 5)
    state = _state(handoff_at=past.isoformat())
    assert is_overdue(state, settings)


def test_only_once_each():
    settings = get_settings()
    past = datetime.now(timezone.utc) - timedelta(minutes=settings.handoff_eta_minutes + 5)
    state = _state(handoff_at=past.isoformat(), eta_notice_count=1)
    assert not is_overdue(state, settings)


def test_quoted_stage_never_overdue():
    settings = get_settings()
    past = datetime.now(timezone.utc) - timedelta(minutes=settings.handoff_eta_minutes + 5)
    state = _state(stage="QUOTED", handoff_at=past.isoformat())
    assert not is_overdue(state, settings)


@pytest.fixture
def agent(seeded):
    session = seeded()
    transport = MockTransport()
    orchestrator = Orchestrator(
        session=session,
        llm=MockLLM(),
        transport=transport,
        settings=get_settings(),
    )
    yield orchestrator, transport, session
    session.close()


def _hand_off(orchestrator, transport, thread="eta-1"):
    orchestrator.handle_message(thread, BUYER, "minta penawaran BM250")
    transport.sent.clear()
    orchestrator.handle_message(thread, BUYER, "2 pcs kirim ke Jakarta")
    return (
        orchestrator.session.query(Conversation)
        .filter(Conversation.wa_thread_id == thread)
        .one()
    )


def test_handoff_message_includes_eta(agent):
    orchestrator, transport, _ = agent
    orchestrator.handle_message("eta-eta", BUYER, "minta penawaran BM250")
    orchestrator.handle_message("eta-eta", BUYER, "2 pcs kirim ke Jakarta")
    buyer_text = " ".join(transport.to(BUYER))
    assert "Estimasi balasan sekitar" in buyer_text
    assert "1 jam" in buyer_text


def test_rfq_marked_sent_to_admin(agent):
    orchestrator, transport, session = agent
    _hand_off(orchestrator, transport)
    rfq = session.query(Rfq).one()
    assert rfq.status == "sent_to_admin"


def test_sweep_notifies_once(agent):
    orchestrator, transport, session = agent
    _hand_off(orchestrator, transport)
    settings = get_settings()
    later = datetime.now(timezone.utc) + timedelta(minutes=settings.handoff_eta_minutes + 1)

    first = sweep_pending_handoffs(session, settings, transport, now=later)
    assert len(first) == 1
    buyer_msgs = transport.to(BUYER)
    assert any("belum membalas" in text for text in buyer_msgs)
    assert any("Reminder" in text for text in transport.to(ADMIN))

    second = sweep_pending_handoffs(session, settings, transport, now=later)
    assert second == []
    assert sum("belum membalas" in text for text in transport.to(BUYER)) == 1

    events = session.query(Event).filter_by(type="handoff_pending").all()
    assert len(events) == 1


def test_dry_run_sends_nothing(agent):
    orchestrator, transport, session = agent
    _hand_off(orchestrator, transport)
    transport.sent.clear()
    settings = get_settings()
    later = datetime.now(timezone.utc) + timedelta(minutes=settings.handoff_eta_minutes + 1)
    rows = sweep_pending_handoffs(session, settings, transport, now=later, dry_run=True)
    assert len(rows) == 1
    assert transport.sent == []


def test_paused_conversation_skipped(agent):
    orchestrator, transport, session = agent
    conversation = _hand_off(orchestrator, transport)
    conversation.paused = True
    session.commit()
    settings = get_settings()
    later = datetime.now(timezone.utc) + timedelta(minutes=settings.handoff_eta_minutes + 1)
    assert sweep_pending_handoffs(session, settings, transport, now=later) == []


def test_admin_reply_clears_notice(agent):
    orchestrator, transport, session = agent
    conversation = _hand_off(orchestrator, transport)
    settings = get_settings()
    later = datetime.now(timezone.utc) + timedelta(minutes=settings.handoff_eta_minutes + 1)
    sweep_pending_handoffs(session, settings, transport, now=later)

    orchestrator.handle_message(conversation.wa_thread_id, ADMIN, "Rp 15.000.000 ya")
    state = ConversationState.from_dict(conversation.state_json)
    assert state.stage == "QUOTED"
    assert state.handoff_at is None
    assert state.eta_notice_count == 0
    assert sweep_pending_handoffs(session, settings, transport, now=later) == []


def test_outside_window_uses_template(agent):
    orchestrator, transport, session = agent
    conversation = _hand_off(orchestrator, transport)
    stale = datetime.now(timezone.utc) - timedelta(days=3)
    session.execute(
        text("UPDATE conversation SET updated_at = :stale WHERE id = :cid"),
        {"stale": stale.isoformat(), "cid": conversation.id},
    )
    session.commit()
    session.refresh(conversation)
    settings = get_settings()
    later = datetime.now(timezone.utc) + timedelta(minutes=settings.handoff_eta_minutes + 1)
    sweep_pending_handoffs(session, settings, transport, now=later)
    assert transport.templates
    assert transport.templates[0]["template"] == "quote_eta"
    assert not any(buyer_notice("RFQ") in text for text in transport.to(BUYER))


def test_lazy_notice_on_buyer_turn(agent):
    orchestrator, transport, session = agent
    conversation = _hand_off(orchestrator, transport)
    state = ConversationState.from_dict(conversation.state_json)
    settings = get_settings()
    past = (
        datetime.now(timezone.utc)
        - timedelta(minutes=settings.handoff_eta_minutes + 5)
    ).isoformat()
    state.handoff_at = past
    conversation.state_json = state.to_dict()
    session.commit()

    transport.sent.clear()
    turn = orchestrator.handle_message(conversation.wa_thread_id, BUYER, "sudah ada harga?")
    assert any("belum membalas" in reply for reply in turn.replies)
    assert any("belum membalas" in text for text in transport.to(BUYER))


def test_mark_handoff_sent_sets_timestamp(agent):
    orchestrator, transport, session = agent
    conversation = _hand_off(orchestrator, transport)
    state = ConversationState.from_dict(conversation.state_json)
    assert state.handoff_at is not None


def test_pending_eta_notice_no_rfq(agent):
    orchestrator, transport, session = agent
    conversation = orchestrator._get_or_create_conversation("eta-empty", BUYER)
    settings = get_settings()
    state = ConversationState(stage="AWAIT_PRICE")
    state.handoff_at = (
        datetime.now(timezone.utc) - timedelta(minutes=settings.handoff_eta_minutes + 5)
    ).isoformat()
    conversation.state_json = state.to_dict()
    session.commit()
    assert pending_eta_notice(session, conversation, settings, transport) is None


def test_mark_handoff_helper_direct(agent):
    orchestrator, transport, session = agent
    conversation = _hand_off(orchestrator, transport)
    rfq = session.query(Rfq).one()
    mark_handoff_sent(session, conversation, rfq.id)
    rfq_after = session.get(Rfq, rfq.id)
    assert rfq_after.status == "sent_to_admin"
