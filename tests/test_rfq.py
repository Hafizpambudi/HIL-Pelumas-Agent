from pelumas_agent.db.models import Event
from pelumas_agent.rfq.service import RfqService
from pelumas_agent.rfq.validator import validate_rfq_payload


def _payload(**overrides):
    base = {
        "items": [{"part_no": "BM250", "name": "Avery Hardoll BM250", "qty": 2}],
        "delivery_city": "Jakarta",
        "urgency": "segera",
        "buyer_type": "engineer",
    }
    base.update(overrides)
    return base


def test_validator_ok():
    ok, missing = validate_rfq_payload(_payload())
    assert ok
    assert missing == []


def test_validator_missing_city():
    ok, missing = validate_rfq_payload(_payload(delivery_city=None))
    assert not ok
    assert "delivery_city" in missing


def test_validator_missing_qty():
    ok, missing = validate_rfq_payload(_payload(items=[{"part_no": "BM250", "qty": None}]))
    assert not ok
    assert "quantity" in missing


def test_validator_missing_items():
    ok, missing = validate_rfq_payload(_payload(items=[]))
    assert not ok
    assert "items" in missing


def test_validator_unresolvable_item():
    ok, missing = validate_rfq_payload(_payload(items=[{"qty": 1}]))
    assert not ok


def test_rfq_id_format(seeded):
    session = seeded()
    try:
        service = RfqService(session, base_url="http://localhost:8000")

        class _Ctx:
            conversation_id = None

        outcome = service.build(_Ctx(), _payload())
        assert outcome["ok"]
        rfq_id = outcome["id"]
        year = rfq_id.split("-")[1]
        month = rfq_id.split("-")[2]
        seq = rfq_id.split("-")[3]
        assert rfq_id.startswith("RFQ-")
        assert len(year) == 4 and len(month) == 2 and len(seq) == 4

        outcome2 = service.build(_Ctx(), _payload())
        assert outcome2["id"].endswith("0002")
    finally:
        session.close()


def test_handoff_format_fits_one_screen(seeded):
    session = seeded()
    try:
        service = RfqService(session, base_url="http://localhost:8000")

        class _Ctx:
            conversation_id = None

        outcome = service.build(_Ctx(), _payload(company="PT Contoh"))
        rfq = service.get(outcome["id"])
        message = service.format_handoff(rfq)
        assert outcome["id"] in message
        assert "BM250" in message
        assert "Jakarta" in message
        assert "PT Contoh" in message
        assert len(message) < 1000
        assert message.count("\n") < 20
    finally:
        session.close()


def test_record_quote_audit(seeded):
    session = seeded()
    try:
        service = RfqService(session, base_url="")

        class _Ctx:
            conversation_id = None

        outcome = service.build(_Ctx(), _payload())
        rfq = service.record_quote(outcome["id"], "6281200000001", "jual 15 juta", "15 juta")
        assert rfq.status == "priced"
        assert rfq.quoted_by == "6281200000001"
        assert rfq.quoted_total == "15 juta"
        assert rfq.quoted_at is not None

        events = session.query(Event).filter_by(type="admin_price").all()
        assert len(events) == 1
        assert events[0].payload["raw_message"] == "jual 15 juta"
    finally:
        session.close()
