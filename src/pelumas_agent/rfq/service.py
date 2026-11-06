from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from pelumas_agent.db.models import Conversation, Event, Rfq
from pelumas_agent.rfq.validator import missing_field_message, validate_rfq_payload


class RfqService:
    def __init__(self, session: Session, base_url: str = ""):
        self.session = session
        self.base_url = base_url.rstrip("/")

    def build(self, tool_ctx, payload: dict) -> dict:
        ok, missing = validate_rfq_payload(payload)
        if not ok:
            return {
                "ok": False,
                "missing": missing,
                "ask_message": missing_field_message(missing),
            }

        rfq_id = self._next_id()
        conversation_id = tool_ctx.conversation_id
        buyer_type = "unknown"
        if conversation_id:
            conversation = self.session.get(Conversation, conversation_id)
            if conversation is not None:
                buyer_type = conversation.buyer_type

        rfq = Rfq(
            id=rfq_id,
            conversation_id=conversation_id,
            company=payload.get("company"),
            contact_name=payload.get("contact_name"),
            buyer_type=payload.get("buyer_type", buyer_type),
            items=payload.get("items", []),
            delivery_city=payload.get("delivery_city"),
            urgency=payload.get("urgency"),
            open_questions=payload.get("open_questions", []),
            status="ready",
        )
        self.session.add(rfq)
        self.session.commit()
        return {"ok": True, "id": rfq_id, "status": rfq.status}

    def _next_id(self) -> str:
        now = datetime.now(timezone.utc)
        prefix = f"RFQ-{now.year}-{now.month:02d}-"
        rows = (
            self.session.execute(select(Rfq.id).where(Rfq.id.like(f"{prefix}%")))
            .scalars()
            .all()
        )
        return f"{prefix}{len(rows) + 1:04d}"

    def format_handoff(self, rfq: Rfq) -> str:
        lines = [f"RFQ baru: {rfq.id}", f"Pembeli: {rfq.buyer_type}"]
        if rfq.company:
            lines.append(f"Perusahaan: {rfq.company}")
        if rfq.contact_name:
            lines.append(f"Kontak: {rfq.contact_name}")
        for item in rfq.items or []:
            name = item.get("part_no") or item.get("name") or "?"
            qty = item.get("qty", "?")
            specs = item.get("specs") or ""
            line = f"- {name} x{qty}"
            if specs:
                line += f" ({specs})"
            lines.append(line)
        if rfq.delivery_city:
            lines.append(f"Kota kirim: {rfq.delivery_city}")
        if rfq.urgency:
            lines.append(f"Urgensi: {rfq.urgency}")
        if rfq.open_questions:
            lines.append("Pertanyaan terbuka: " + "; ".join(rfq.open_questions))
        if self.base_url:
            lines.append(f"Detail: {self.base_url}/rfq/{rfq.id}")
        return "\n".join(lines)

    def record_quote(
        self, rfq_id: str, admin_phone: str, raw_text: str, quoted_total: str
    ) -> Rfq | None:
        rfq = self.session.get(Rfq, rfq_id)
        if rfq is None:
            return None
        rfq.quoted_total = quoted_total
        rfq.quoted_by = admin_phone
        rfq.quoted_at = datetime.now(timezone.utc)
        rfq.status = "priced"
        self.session.add(
            Event(
                conversation_id=rfq.conversation_id,
                type="admin_price",
                payload={
                    "rfq_id": rfq_id,
                    "admin": admin_phone,
                    "raw_message": raw_text,
                    "quoted_total": quoted_total,
                },
            )
        )
        self.session.commit()
        return rfq

    def get(self, rfq_id: str) -> Rfq | None:
        return self.session.get(Rfq, rfq_id)
