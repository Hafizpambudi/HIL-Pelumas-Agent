from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from pelumas_agent.availability.base import AvailabilityAdapter, check_availability
from pelumas_agent.config import Settings, get_settings
from pelumas_agent.db.models import Equivalence, Event, Product
from pelumas_agent.retrieval.search import exact_lookup, search_tiered


@dataclass
class ToolContext:
    session: Session
    embedder: object | None = None
    adapter: AvailabilityAdapter | None = None
    conversation_id: str | None = None
    settings: Settings = field(default_factory=get_settings)
    rfq_service: object | None = None
    handoff_sender: object | None = None


def product_to_dict(product: Product, include_description: bool = True) -> dict:
    specs = []
    for spec in product.specs:
        specs.append(
            {
                "key": spec.key,
                "value_num": spec.value_num,
                "value_text": spec.value_text,
                "unit": spec.unit,
                "source": spec.source,
                "confidence": spec.confidence,
            }
        )
    data = {
        "part_no": product.part_no,
        "name": product.name,
        "brand": product.brand,
        "category": product.category,
        "status": product.status,
        "data_confidence": product.data_confidence,
        "specs": specs,
    }
    if include_description and product.description_id:
        data["description"] = product.description_id
    return data


def _log_event(ctx: ToolContext, type_: str, payload: dict) -> None:
    ctx.session.add(
        Event(conversation_id=ctx.conversation_id, type=type_, payload=payload)
    )
    ctx.session.commit()


def tool_search_products(ctx: ToolContext, args: dict) -> dict:
    query = args.get("query", "")
    tier, products = search_tiered(
        ctx.session,
        query,
        embedder=ctx.embedder,
        category=args.get("category"),
        fluid=args.get("fluid"),
        connection_size_in=args.get("connection_size_in"),
        flow_lpm=args.get("flow_lpm"),
        min_pressure_bar=args.get("min_pressure_bar"),
    )
    return {
        "tier": tier,
        "products": [product_to_dict(p, include_description=False) for p in products],
    }


def tool_get_product(ctx: ToolContext, args: dict) -> dict:
    ref = args.get("part_no") or args.get("query", "")
    hits = exact_lookup(ctx.session, ref)
    if not hits:
        return {"found": False, "query": ref}
    return {"found": True, "products": [product_to_dict(p) for p in hits[:3]]}


def tool_compare_specs(ctx: ToolContext, args: dict) -> dict:
    refs = args.get("part_nos") or []
    products = []
    for ref in refs[:4]:
        hits = exact_lookup(ctx.session, str(ref))
        if hits:
            products.append(hits[0])
    if len(products) < 2:
        return {"error": "butuh minimal dua part yang ditemukan", "found": len(products)}

    keys: set[str] = set()
    for product in products:
        keys.update(s.key for s in product.specs)
    dimensions = args.get("dimensions") or sorted(keys)

    rows = []
    for key in dimensions:
        values = []
        for product in products:
            spec = next((s for s in product.specs if s.key == key), None)
            if spec is None:
                values.append("tidak dipublikasikan")
            elif spec.value_text:
                values.append(spec.value_text)
            else:
                values.append(str(spec.value_num))
        if len(set(values)) > 1:
            rows.append(
                {
                    "dimension": key,
                    "values": {p.name: v for p, v in zip(products, values, strict=True)},
                }
            )
    return {
        "products": [p.name for p in products],
        "differing_dimensions": rows,
    }


def tool_find_equivalent(ctx: ToolContext, args: dict) -> dict:
    ref = args.get("part_no", "")
    hits = exact_lookup(ctx.session, ref)
    if not hits:
        return {"found": False, "query": ref}
    product = hits[0]
    pairs = (
        ctx.session.execute(
            select(Equivalence).where(
                (Equivalence.a_product_id == product.id)
                | (Equivalence.b_product_id == product.id)
            )
        )
        .scalars()
        .all()
    )
    equivalents = []
    for pair in pairs:
        other_id = pair.b_product_id if pair.a_product_id == product.id else pair.a_product_id
        other = ctx.session.get(Product, other_id)
        if other is None or other.status == "discontinued":
            continue
        equivalents.append(
            {
                "name": other.name,
                "part_no": other.part_no,
                "relation": pair.relation,
                "differing_dims": pair.differing_dims,
                "confidence": pair.confidence,
                "verified_by": pair.verified_by,
                "label": (
                    "interchangeable"
                    if pair.confidence == "high"
                    else "kandidat, perlu konfirmasi teknis"
                ),
            }
        )
    return {"found": True, "product": product.name, "equivalents": equivalents[:2]}


def tool_check_availability(ctx: ToolContext, args: dict) -> dict:
    part_no = args.get("part_no", "")
    qty = args.get("qty")
    if ctx.adapter is None:
        return {"error": "availability adapter not configured"}
    result = check_availability(ctx.session, ctx.adapter, part_no, qty)
    _log_event(
        ctx,
        "tool_call",
        {"tool": "check_availability", "part_no": part_no, "state": result.state},
    )
    return {
        "part_no": result.part_no,
        "state": result.state,
        "source": result.source,
        "observed_at": result.observed_at.isoformat(),
        "note": result.note,
        "lead_time_days": result.lead_time_days,
    }


def tool_create_rfq(ctx: ToolContext, args: dict) -> dict:
    if ctx.rfq_service is None:
        return {"error": "rfq service not configured"}
    payload = args.get("payload", args)
    outcome = ctx.rfq_service.build(ctx, payload)
    _log_event(ctx, "rfq_created" if outcome.get("ok") else "tool_call",
               {"tool": "create_rfq", "outcome": outcome})
    return outcome


def tool_handoff(ctx: ToolContext, args: dict) -> dict:
    reason = args.get("reason", "handoff")
    summary = args.get("summary", "")
    _log_event(ctx, "handoff", {"reason": reason, "summary": summary})
    if ctx.handoff_sender is not None:
        ctx.handoff_sender(reason, summary)
    return {"status": "handed_off", "reason": reason}


def tool_log_event(ctx: ToolContext, args: dict) -> dict:
    _log_event(ctx, args.get("type", "tool_call"), args.get("payload", {}))
    return {"status": "logged"}


TOOL_FUNCTIONS = {
    "search_products": tool_search_products,
    "get_product": tool_get_product,
    "compare_specs": tool_compare_specs,
    "find_equivalent": tool_find_equivalent,
    "check_availability": tool_check_availability,
    "create_rfq": tool_create_rfq,
    "handoff": tool_handoff,
    "log_event": tool_log_event,
}

TOOL_SCHEMAS = [
    {
        "name": "search_products",
        "description": (
            "Cari produk di katalog. Exact part number diutamakan, "
            "lalu filter terstruktur, lalu semantik."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "category": {"type": "string"},
                "fluid": {"type": "string"},
                "connection_size_in": {"type": "number"},
                "flow_lpm": {"type": "number"},
                "min_pressure_bar": {"type": "number"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_product",
        "description": "Ambil detail satu produk berdasarkan part number atau nama.",
        "parameters": {
            "type": "object",
            "properties": {
                "part_no": {"type": "string"},
                "query": {"type": "string"},
            },
        },
    },
    {
        "name": "compare_specs",
        "description": (
            "Bandingkan spesifikasi dua produk atau lebih; "
            "hanya dimensi yang berbeda yang ditampilkan."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "part_nos": {"type": "array", "items": {"type": "string"}},
                "dimensions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["part_nos"],
        },
    },
    {
        "name": "find_equivalent",
        "description": (
            "Cari produk ekuivalen dari tabel kurasi. "
            "Hanya confidence=high yang boleh disebut interchangeable."
        ),
        "parameters": {
            "type": "object",
            "properties": {"part_no": {"type": "string"}},
            "required": ["part_no"],
        },
    },
    {
        "name": "check_availability",
        "description": (
            "Cek ketersediaan. Hasil: available, indent, unknown, atau discontinued. "
            "Jangan klaim stok di luar hasil ini."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "part_no": {"type": "string"},
                "qty": {"type": "integer"},
            },
            "required": ["part_no"],
        },
    },
    {
        "name": "create_rfq",
        "description": "Buat RFQ. Wajib: minimal satu item yang jelas, qty, dan kota pengiriman.",
        "parameters": {
            "type": "object",
            "properties": {
                "payload": {"type": "object"},
            },
        },
    },
    {
        "name": "handoff",
        "description": "Serahkan percakapan ke admin dengan alasan dan ringkasan.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
                "summary": {"type": "string"},
            },
            "required": ["reason"],
        },
    },
    {
        "name": "log_event",
        "description": "Catat event internal.",
        "parameters": {
            "type": "object",
            "properties": {
                "type": {"type": "string"},
                "payload": {"type": "object"},
            },
        },
    },
]


def dispatch_tool(ctx: ToolContext, name: str, args: dict) -> dict:
    function = TOOL_FUNCTIONS.get(name)
    if function is None:
        return {"error": f"unknown tool: {name}"}
    return function(ctx, args)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
