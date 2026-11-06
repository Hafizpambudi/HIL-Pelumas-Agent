import json
from dataclasses import dataclass, field

STAGES = [
    "NEW",
    "IDENTIFY",
    "QUALIFY",
    "RESOLVE",
    "FIT_CHECK",
    "CONFIGURE",
    "UNRESOLVED",
    "AVAILABILITY",
    "SUBSTITUTE",
    "RFQ",
    "HANDOFF",
    "AWAIT_PRICE",
    "QUOTED",
    "CLOSED",
    "LOST",
    "DORMANT",
]


@dataclass
class ConversationState:
    stage: str = "NEW"
    buyer_type: str = "unknown"
    company: str | None = None
    contact_name: str | None = None
    delivery_city: str | None = None
    urgency: str | None = None
    resolved_part_no: str | None = None
    resolved_name: str | None = None
    items: list[dict] = field(default_factory=list)
    requirements: dict = field(default_factory=dict)
    availability_state: str | None = None
    availability_source: str | None = None
    rfq_id: str | None = None
    questions_asked: int = 0
    failed_clarifications: int = 0
    asked_missing_fields: bool = False
    price_asked: bool = False
    handoff_at: str | None = None
    eta_notice_count: int = 0
    language: str = "id"
    history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "buyer_type": self.buyer_type,
            "company": self.company,
            "contact_name": self.contact_name,
            "delivery_city": self.delivery_city,
            "urgency": self.urgency,
            "resolved_part_no": self.resolved_part_no,
            "resolved_name": self.resolved_name,
            "items": self.items,
            "requirements": self.requirements,
            "availability_state": self.availability_state,
            "availability_source": self.availability_source,
            "rfq_id": self.rfq_id,
            "questions_asked": self.questions_asked,
            "failed_clarifications": self.failed_clarifications,
            "asked_missing_fields": self.asked_missing_fields,
            "price_asked": self.price_asked,
            "handoff_at": self.handoff_at,
            "eta_notice_count": self.eta_notice_count,
            "language": self.language,
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "ConversationState":
        state = cls()
        if not data:
            return state
        for key, value in data.items():
            if hasattr(state, key):
                setattr(state, key, value)
        return state

    def add_history(self, role: str, text: str, max_messages: int = 12) -> None:
        self.history.append({"role": role, "content": text})
        overflow = len(self.history) - max_messages
        if overflow > 0:
            self.history = self.history[overflow:]

    def summary_text(self) -> str:
        parts = [f"stage={self.stage}", f"buyer_type={self.buyer_type}"]
        if self.company:
            parts.append(f"company={self.company}")
        if self.resolved_part_no:
            parts.append(f"part={self.resolved_part_no}")
        if self.resolved_name:
            parts.append(f"product={self.resolved_name}")
        if self.items:
            parts.append(f"items={json.dumps(self.items, ensure_ascii=False)}")
        if self.requirements:
            parts.append(f"requirements={json.dumps(self.requirements, ensure_ascii=False)}")
        if self.delivery_city:
            parts.append(f"city={self.delivery_city}")
        if self.urgency:
            parts.append(f"urgency={self.urgency}")
        if self.availability_state:
            parts.append(f"availability={self.availability_state}")
        if self.rfq_id:
            parts.append(f"rfq={self.rfq_id}")
        return "; ".join(parts)
