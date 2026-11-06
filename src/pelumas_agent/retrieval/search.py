import math
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from pelumas_agent.config import get_settings
from pelumas_agent.db.models import Product

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _norm(text: str) -> str:
    return _NON_ALNUM.sub("", text.lower())


def _tokens(text: str) -> set[str]:
    return {t for t in _NON_ALNUM.split(text.lower()) if t}


def exact_lookup(session: Session, query: str) -> list[Product]:
    q = _norm(query)
    if not q:
        return []
    products = session.execute(select(Product)).scalars().all()
    hits: list[Product] = []
    for product in products:
        if product.part_no and _norm(product.part_no) == q:
            hits.append(product)
            continue
        if any(_norm(str(alias)) == q for alias in product.aliases or []):
            hits.append(product)
            continue
    if hits:
        return hits

    query_tokens = _tokens(query)
    contained: list[Product] = []
    for product in products:
        if product.part_no:
            part_tokens = _tokens(product.part_no)
            if part_tokens and part_tokens <= query_tokens:
                contained.append(product)
                continue
        if any(
            alias_tokens and alias_tokens <= query_tokens
            for alias_tokens in (_tokens(str(alias)) for alias in product.aliases or [])
        ):
            contained.append(product)
    if contained:
        return contained

    for product in products:
        name_tokens = _tokens(product.name)
        brand_tokens = _tokens(product.brand)
        part_tokens = _tokens(product.part_no or "")
        alias_tokens: set[str] = set()
        for alias in product.aliases or []:
            alias_tokens |= _tokens(str(alias))
        if query_tokens and query_tokens <= (name_tokens | alias_tokens):
            hits.append(product)
            continue
        model_match = (query_tokens & (part_tokens | alias_tokens)) - brand_tokens
        if query_tokens & brand_tokens and model_match:
            hits.append(product)
    return hits


def filtered_lookup(
    session: Session,
    category: str | None = None,
    fluid: str | None = None,
    connection_size_in: float | None = None,
    flow_lpm: float | None = None,
    min_pressure_bar: float | None = None,
    include_discontinued: bool = False,
) -> list[Product]:
    products = session.execute(select(Product)).scalars().all()
    results = []
    for product in products:
        if not include_discontinued and product.status == "discontinued":
            continue
        if category and product.category != category:
            continue
        specs = {s.key: s for s in product.specs}
        if fluid:
            fluid_spec = specs.get("fluid")
            if not fluid_spec or fluid.lower() not in (fluid_spec.value_text or "").lower():
                continue
        if connection_size_in is not None:
            size_spec = specs.get("connection_size_in")
            if size_spec is None or size_spec.value_num is None:
                continue
            if abs(size_spec.value_num - connection_size_in) > 1e-9:
                continue
        if flow_lpm is not None:
            flow_min = specs.get("flow_min_lpm")
            flow_max = specs.get("flow_max_lpm")
            if flow_max is None or flow_max.value_num is None:
                continue
            if flow_lpm > flow_max.value_num:
                continue
            if (
                flow_min is not None
                and flow_min.value_num is not None
                and flow_lpm < flow_min.value_num
            ):
                continue
        if min_pressure_bar is not None:
            pressure_spec = specs.get("max_pressure_bar")
            if pressure_spec is None or pressure_spec.value_num is None:
                continue
            if pressure_spec.value_num < min_pressure_bar:
                continue
        results.append(product)
    return results


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def semantic_lookup(
    session: Session, query: str, embedder, limit: int | None = None, threshold: float = 0.05
) -> list[tuple[Product, float]]:
    limit = limit or get_settings().max_retrieved_products
    vector = embedder.embed([query])[0]
    products = session.execute(select(Product)).scalars().all()
    scored = []
    for product in products:
        if product.status == "discontinued":
            continue
        if product.embedding is None:
            continue
        score = _cosine(vector, product.embedding)
        if score >= threshold:
            scored.append((product, score))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:limit]


def search_tiered(
    session: Session,
    query: str,
    embedder=None,
    category: str | None = None,
    fluid: str | None = None,
    connection_size_in: float | None = None,
    flow_lpm: float | None = None,
    min_pressure_bar: float | None = None,
) -> tuple[str, list[Product]]:
    limit = get_settings().max_retrieved_products

    exact = exact_lookup(session, query)
    if exact:
        return "exact", exact[:limit]

    has_filters = any(
        value is not None
        for value in (category, fluid, connection_size_in, flow_lpm, min_pressure_bar)
    )
    if has_filters:
        filtered = filtered_lookup(
            session,
            category=category,
            fluid=fluid,
            connection_size_in=connection_size_in,
            flow_lpm=flow_lpm,
            min_pressure_bar=min_pressure_bar,
        )
        if filtered:
            return "filtered", filtered[:limit]

    if embedder is not None:
        semantic = semantic_lookup(session, query, embedder)
        if semantic:
            return "semantic", [p for p, _ in semantic]

    return "none", []
