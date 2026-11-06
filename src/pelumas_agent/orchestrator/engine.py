import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from pelumas_agent.availability.adapters import get_adapter
from pelumas_agent.config import Settings, get_settings
from pelumas_agent.db.models import Conversation, Event, Rfq
from pelumas_agent.fitment.rules import FitmentRequirement, evaluate_fitment
from pelumas_agent.guards.outbound import GuardContext, run_guards
from pelumas_agent.handoff import format_eta, mark_handoff_sent, pending_eta_notice
from pelumas_agent.orchestrator.extract import (
    detect_intent,
    detect_language,
    extract_city,
    extract_connection_size,
    extract_flow_lpm,
    extract_fluid,
    extract_pressure_bar,
    extract_price_amount,
    extract_qty,
)
from pelumas_agent.orchestrator.prompts import SYSTEM_PROMPT, build_context_messages
from pelumas_agent.orchestrator.state import ConversationState
from pelumas_agent.retrieval.search import exact_lookup
from pelumas_agent.rfq.service import RfqService
from pelumas_agent.tools.registry import TOOL_SCHEMAS, ToolContext, dispatch_tool

PAUSE_KEYWORDS = {"pause", "ambil alih", "jeda", "takeover"}
RESUME_KEYWORDS = {"resume", "lanjutkan", "lanjut"}
MAX_TOOL_ITERATIONS = 5

FITMENT_LABELS = {
    "connection_size_in": "ukuran sambungan",
    "max_pressure_bar": "tekanan kerja",
    "flow_range": "rentang aliran",
    "fluid": "fluida",
    "flange_rating": "rating flange",
    "accuracy_pct": "akurasi",
}


@dataclass
class AgentTurn:
    replies: list[str] = field(default_factory=list)
    stage: str = "NEW"
    tool_calls: list[dict] = field(default_factory=list)
    guard_blocks: list[str] = field(default_factory=list)


class Orchestrator:
    def __init__(
        self,
        session: Session,
        llm,
        embedder=None,
        adapter=None,
        transport=None,
        settings: Settings | None = None,
    ):
        self.session = session
        self.llm = llm
        self.embedder = embedder
        self.adapter = adapter or get_adapter()
        self.transport = transport
        self.settings = settings or get_settings()
        self.rfq_service = RfqService(session, self.settings.base_url)

    def handle_message(
        self, wa_thread_id: str, from_phone: str, text: str
    ) -> AgentTurn:
        conversation = self._get_or_create_conversation(wa_thread_id, from_phone)

        if from_phone in self.settings.admin_numbers:
            return self._handle_admin(conversation, from_phone, text)

        if conversation.paused:
            self._log_event(conversation.id, "message_in", {"text": text, "from": from_phone})
            return AgentTurn(stage=conversation.stage)

        overdue_notice = pending_eta_notice(
            self.session, conversation, self.settings, self.transport
        )

        state = ConversationState.from_dict(conversation.state_json)
        state.add_history("user", text, self.settings.max_context_messages)
        self._log_event(conversation.id, "message_in", {"text": text, "from": from_phone})

        overdue_replies: list[str] = []
        if overdue_notice:
            overdue_replies.append(overdue_notice)
            state.add_history("assistant", overdue_notice, self.settings.max_context_messages)

        old_city = state.delivery_city
        old_urgency = state.urgency
        old_requirements = dict(state.requirements)
        old_items = [dict(item) for item in state.items]
        self._update_entities(state, text)
        entities_changed = (
            state.delivery_city != old_city
            or state.urgency != old_urgency
            or state.requirements != old_requirements
            or state.items != old_items
        )
        intents = detect_intent(text)

        turn = AgentTurn()

        if intents["negotiation"]:
            self._handoff(conversation, state, "negosiasi", text, turn)
            self._persist(conversation, state, state.stage)
            return turn

        fitment_sentence = self._maybe_fitment(state)

        if self._is_state_update(state, text, intents, entities_changed):
            llm_text, tool_calls, backing = None, [], {
                "stock_confirmed": False,
                "fitment_backed": False,
                "equivalence_backed": False,
            }
        else:
            llm_text, tool_calls, backing = self._llm_loop(conversation, state, text)
        turn.tool_calls = tool_calls

        self._post_tools(conversation, state, intents, turn)

        replies: list[str] = []
        if llm_text:
            replies.append(llm_text)
        if fitment_sentence:
            replies.append(fitment_sentence)

        rfq_sentence = self._maybe_rfq(conversation, state, intents, turn)
        if rfq_sentence:
            replies.append(rfq_sentence)
        replies.extend(turn.replies)

        guarded = self._guard_text(conversation, replies, backing)
        for reply in guarded:
            state.add_history("assistant", reply, self.settings.max_context_messages)
        turn.replies = guarded + overdue_replies
        turn.guard_blocks = []

        if self.transport and not conversation.paused:
            for reply in guarded:
                self.transport.send(from_phone, reply)

        turn.stage = state.stage
        self._persist(conversation, state, state.stage)
        self._log_event(conversation.id, "message_out", {"texts": turn.replies})
        return turn

    def _get_or_create_conversation(self, wa_thread_id: str, from_phone: str) -> Conversation:
        conversation = (
            self.session.execute(
                select(Conversation).where(Conversation.wa_thread_id == wa_thread_id)
            )
            .scalars()
            .first()
        )
        if conversation is None:
            conversation = Conversation(wa_thread_id=wa_thread_id, buyer_phone=from_phone)
            self.session.add(conversation)
            self.session.commit()
        return conversation

    def _handle_admin(self, conversation: Conversation, admin_phone: str, text: str) -> AgentTurn:
        lowered = text.strip().lower()
        turn = AgentTurn(stage=conversation.stage)

        if lowered in PAUSE_KEYWORDS:
            conversation.paused = True
            conversation.assigned_admin = admin_phone
            self._log_event(
                conversation.id, "handoff", {"reason": "admin_override", "admin": admin_phone}
            )
            self._persist(
                conversation,
                ConversationState.from_dict(conversation.state_json),
                conversation.stage,
            )
            turn.replies = ["Agent dijeda. Percakapan ini Anda pegang penuh."]
            return turn

        if lowered in RESUME_KEYWORDS:
            conversation.paused = False
            conversation.assigned_admin = None
            self._log_event(
                conversation.id, "handoff", {"reason": "admin_resume", "admin": admin_phone}
            )
            self._persist(
                conversation,
                ConversationState.from_dict(conversation.state_json),
                conversation.stage,
            )
            turn.replies = ["Agent aktif kembali untuk percakapan ini."]
            return turn

        self._log_event(conversation.id, "message_in", {"text": text, "from": admin_phone})

        amount = extract_price_amount(text)
        rfq = self._active_rfq(conversation)
        if amount and rfq:
            self.rfq_service.record_quote(rfq.id, admin_phone, text, amount)
            relay = (
                f"Update untuk {rfq.id}: admin kami memberikan penawaran "
                f"{amount}. Terima kasih sudah menunggu."
            )
            outcome = run_guards(relay, GuardContext(admin_relay=True))
            final = relay if outcome.passed else (outcome.fallback or relay)
            state = ConversationState.from_dict(conversation.state_json)
            state.stage = "QUOTED"
            state.handoff_at = None
            state.eta_notice_count = 0
            state.add_history("assistant", final, self.settings.max_context_messages)
            conversation.stage = "QUOTED"
            self._persist(conversation, state, "QUOTED")
            if self.transport and conversation.buyer_phone:
                self.transport.send(conversation.buyer_phone, final)
            self._log_event(conversation.id, "message_out", {"texts": [final], "relay": True})
            turn.replies = [final]
            turn.stage = "QUOTED"
            return turn

        return turn

    def _active_rfq(self, conversation: Conversation) -> Rfq | None:
        state = ConversationState.from_dict(conversation.state_json)
        if state.rfq_id:
            rfq = self.rfq_service.get(state.rfq_id)
            if rfq:
                return rfq
        return (
            self.session.execute(
                select(Rfq)
                .where(Rfq.conversation_id == conversation.id)
                .order_by(Rfq.created_at.desc())
            )
            .scalars()
            .first()
        )

    def _is_state_update(
        self,
        state: ConversationState,
        text: str,
        intents: dict,
        entities_changed: bool,
    ) -> bool:
        if not state.resolved_part_no:
            return False
        if not entities_changed:
            return False
        if any(
            intents[key]
            for key in (
                "price",
                "negotiation",
                "availability",
                "substitution",
                "comparison",
                "bot_question",
            )
        ):
            return False
        hits = exact_lookup(self.session, text)
        if hits and hits[0].part_no and hits[0].part_no != state.resolved_part_no:
            return False
        return True

    def _update_entities(self, state: ConversationState, text: str) -> None:
        state.language = detect_language(text)
        intents = detect_intent(text)
        if intents["urgency"] and not state.urgency:
            state.urgency = "segera"

        if state.buyer_type == "unknown":
            lowered = text.lower()
            procurement_words = ("penawaran", "invoice", "npwp", "quotation", "po ")
            project_words = ("proyek", "project", "spbu", "instalasi", "depot", "buat ")
            if any(word in lowered for word in procurement_words):
                state.buyer_type = "procurement"
            elif any(word in lowered for word in project_words):
                state.buyer_type = "project"
            elif (
                state.resolved_part_no
                or extract_connection_size(text)
                or extract_pressure_bar(text)
            ):
                state.buyer_type = "engineer"

        city = extract_city(text)
        if city:
            state.delivery_city = city

        qty = extract_qty(text)
        fluid = extract_fluid(text)
        if fluid:
            state.requirements["fluid"] = fluid
        size = extract_connection_size(text)
        if size is not None:
            state.requirements["connection_size_in"] = size
        pressure = extract_pressure_bar(text)
        if pressure is not None:
            state.requirements["system_pressure_bar"] = pressure
        flow = extract_flow_lpm(text)
        if flow is not None:
            state.requirements["flow_lpm"] = flow

        if qty:
            if state.items:
                for item in state.items:
                    item["qty"] = qty
            else:
                state.items.append(
                    {
                        "part_no": state.resolved_part_no,
                        "name": state.resolved_name,
                        "qty": qty,
                    }
                )

        if intents["price"]:
            state.price_asked = True

    def _resolve_product(self, state: ConversationState, text: str) -> None:
        if state.resolved_part_no:
            return
        hits = exact_lookup(self.session, text)
        if len(hits) == 1:
            state.resolved_part_no = hits[0].part_no
            state.resolved_name = hits[0].name
            if not state.items:
                state.items.append(
                    {"part_no": hits[0].part_no, "name": hits[0].name, "qty": None}
                )
            elif not state.items[0].get("part_no"):
                state.items[0]["part_no"] = hits[0].part_no
                state.items[0]["name"] = hits[0].name

    def _maybe_fitment(self, state: ConversationState) -> str | None:
        if not state.resolved_part_no or not state.requirements:
            return None
        hits = exact_lookup(self.session, state.resolved_part_no)
        if not hits:
            return None
        requirement = FitmentRequirement(
            connection_size_in=state.requirements.get("connection_size_in"),
            system_pressure_bar=state.requirements.get("system_pressure_bar"),
            flow_lpm=state.requirements.get("flow_lpm"),
            fluid=state.requirements.get("fluid"),
            flange_rating=state.requirements.get("flange_rating"),
            accuracy_pct=state.requirements.get("accuracy_pct"),
        )
        if not requirement.has_any():
            return None
        result = evaluate_fitment(hits[0], requirement)
        state.stage = "FIT_CHECK"
        if result.verdict == "fit":
            dims = ", ".join(FITMENT_LABELS.get(d, d) for d in result.checked)
            return f"Cek kecocokan untuk {dims}: sesuai dengan data spesifikasi."
        if result.verdict == "does_not_fit":
            label = FITMENT_LABELS.get(result.dimension or "", result.dimension)
            return f"Cek kecocokan: tidak lolos di {label}. {result.detail.capitalize()}."
        label = FITMENT_LABELS.get(result.dimension or "", "dimensi ini")
        return f"Cek kecocokan untuk {label}: {result.detail}, perlu konfirmasi dulu ya."

    def _llm_loop(self, conversation: Conversation, state: ConversationState, text: str):
        backing = {"stock_confirmed": False, "fitment_backed": False, "equivalence_backed": False}
        tool_calls: list[dict] = []

        self._resolve_product(state, text)

        context = build_context_messages(state, self.settings.max_context_messages)
        messages = [
            {"role": entry["role"], "content": entry["content"]} for entry in context
        ]

        ctx = ToolContext(
            session=self.session,
            embedder=self.embedder,
            adapter=self.adapter,
            conversation_id=conversation.id,
            settings=self.settings,
            rfq_service=RfqToolBridge(self),
            handoff_sender=None,
        )

        llm_text: str | None = None
        for _ in range(MAX_TOOL_ITERATIONS):
            response = self.llm.complete(
                SYSTEM_PROMPT, _to_llm_messages(messages), TOOL_SCHEMAS
            )
            if not response.tool_calls:
                llm_text = response.text or ""
                break
            for call in response.tool_calls:
                result = dispatch_tool(ctx, call.name, call.arguments)
                tool_calls.append(
                    {"name": call.name, "arguments": call.arguments, "result": result}
                )
                self._log_event(
                    conversation.id,
                    "tool_call",
                    {"name": call.name, "arguments": call.arguments},
                )
                self._apply_tool_backing(call.name, result, backing, state)
                messages.append({"role": "tool", "content": json.dumps(result, ensure_ascii=False)})
                if call.name == "handoff":
                    llm_text = llm_text or "Baik, saya teruskan ke admin kami ya. Mohon ditunggu."
                    state.stage = "HANDOFF"
                    return llm_text, tool_calls, backing
        if llm_text is None:
            llm_text = "Sebentar, saya teruskan ke admin kami ya."
        return llm_text, tool_calls, backing

    def _apply_tool_backing(
        self, name: str, result: dict, backing: dict, state: ConversationState
    ) -> None:
        if name == "check_availability":
            state.availability_state = result.get("state")
            state.availability_source = result.get("source")
            state.stage = "AVAILABILITY"
            if result.get("state") == "available" and result.get("source") != "manual":
                backing["stock_confirmed"] = True
        elif name == "find_equivalent":
            backing["equivalence_backed"] = True
            if state.availability_state == "discontinued":
                state.stage = "SUBSTITUTE"
        elif name == "search_products":
            products = result.get("products", [])
            if result.get("tier") == "exact" and len(products) == 1:
                product = products[0]
                state.resolved_part_no = product.get("part_no") or state.resolved_part_no
                state.resolved_name = product.get("name")
                if state.items and not state.items[0].get("part_no"):
                    state.items[0]["part_no"] = product.get("part_no")
                    state.items[0]["name"] = product.get("name")
                state.stage = "RESOLVE"
            elif result.get("tier") == "none" or not products:
                state.failed_clarifications += 1
                state.stage = "UNRESOLVED"
            else:
                state.stage = "QUALIFY"
        elif name == "get_product":
            products = result.get("products", [])
            if result.get("found") and products:
                product = products[0]
                state.resolved_part_no = product.get("part_no") or state.resolved_part_no
                state.resolved_name = product.get("name")
                state.stage = "RESOLVE"

    def _post_tools(
        self, conversation: Conversation, state: ConversationState, intents: dict, turn: AgentTurn
    ) -> None:
        if state.stage == "UNRESOLVED" and state.failed_clarifications >= 2:
            self._handoff(
                conversation,
                state,
                "item tidak ditemukan setelah klarifikasi",
                json.dumps(state.items, ensure_ascii=False),
                turn,
            )

    def _maybe_rfq(
        self,
        conversation: Conversation,
        state: ConversationState,
        intents: dict,
        turn: AgentTurn,
    ) -> str | None:
        if state.rfq_id:
            return None
        if not (state.price_asked or intents["price"]):
            return None
        resolvable_items = [
            item
            for item in state.items
            if (item.get("part_no") or item.get("name"))
        ]
        if not resolvable_items and not (state.resolved_part_no or state.resolved_name):
            return None

        payload = {
            "company": state.company,
            "contact_name": state.contact_name,
            "buyer_type": state.buyer_type,
            "items": resolvable_items
            or [
                {
                    "part_no": state.resolved_part_no,
                    "name": state.resolved_name,
                    "qty": None,
                }
            ],
            "delivery_city": state.delivery_city,
            "urgency": state.urgency,
            "open_questions": [],
        }
        ctx = ToolContext(
            session=self.session,
            conversation_id=conversation.id,
            settings=self.settings,
            rfq_service=RfqToolBridge(self),
        )
        outcome = dispatch_tool(ctx, "create_rfq", {"payload": payload})
        if outcome.get("ok"):
            state.rfq_id = outcome["id"]
            state.stage = "AWAIT_PRICE"
            rfq = self.rfq_service.get(outcome["id"])
            if rfq and self.transport:
                for admin in self.settings.admin_numbers:
                    self.transport.send(admin, self.rfq_service.format_handoff(rfq))
            state.handoff_at = datetime.now(timezone.utc).isoformat()
            state.eta_notice_count = 0
            mark_handoff_sent(self.session, conversation, outcome["id"])
            return (
                f"RFQ {outcome['id']} sudah saya buat dan teruskan ke admin. "
                f"Estimasi balasan sekitar {format_eta(self.settings.handoff_eta_minutes)} "
                "pada jam kerja. Begitu ada harga, saya langsung kabari di sini."
            )
        ask_message = outcome.get("ask_message")
        if state.asked_missing_fields:
            self._handoff(
                conversation,
                state,
                "RFQ belum lengkap",
                json.dumps(payload, ensure_ascii=False),
                turn,
            )
            return None
        state.asked_missing_fields = True
        return ask_message

    def _handoff(
        self,
        conversation: Conversation,
        state: ConversationState,
        reason: str,
        summary: str,
        turn: AgentTurn,
    ) -> None:
        self._log_event(conversation.id, "handoff", {"reason": reason, "summary": summary})
        state.stage = "HANDOFF"
        if self.transport:
            for admin in self.settings.admin_numbers:
                self.transport.send(
                    admin,
                    f"Handoff ({reason}) dari {conversation.buyer_phone}: {summary}",
                )
        turn.replies.append(
            "Saya teruskan ke admin kami ya. Estimasi balasan sekitar "
            f"{format_eta(self.settings.handoff_eta_minutes)} pada jam kerja."
        )

    def _guard_text(
        self, conversation: Conversation, replies: list[str], backing: dict
    ) -> list[str]:
        guarded: list[str] = []
        for text in replies:
            if not text:
                continue
            ctx = GuardContext(
                stock_confirmed=backing.get("stock_confirmed", False),
                fitment_backed=backing.get("fitment_backed", False)
                or conversation.stage == "FIT_CHECK",
                equivalence_backed=backing.get("equivalence_backed", False),
            )
            outcome = run_guards(text, ctx)
            if outcome.passed:
                guarded.append(text)
            else:
                self._log_event(
                    conversation.id,
                    "guard_block",
                    {"original": text, "blocks": outcome.blocks},
                )
                if outcome.fallback:
                    guarded.append(outcome.fallback)
        return guarded

    def _persist(self, conversation: Conversation, state: ConversationState, stage: str) -> None:
        conversation.stage = stage
        conversation.buyer_type = state.buyer_type
        conversation.state_json = state.to_dict()
        conversation.updated_at = datetime.now(timezone.utc)
        self.session.commit()

    def _log_event(self, conversation_id: str | None, type_: str, payload: dict) -> None:
        self.session.add(Event(conversation_id=conversation_id, type=type_, payload=payload))
        self.session.commit()


class RfqToolBridge:
    def __init__(self, orchestrator: Orchestrator):
        self._orchestrator = orchestrator

    def build(self, tool_ctx: ToolContext, payload: dict) -> dict:
        return self._orchestrator.rfq_service.build(tool_ctx, payload)


def _to_llm_messages(messages: list[dict]):
    from pelumas_agent.llm.base import LLMMessage

    return [LLMMessage(role=entry["role"], content=entry["content"]) for entry in messages]
