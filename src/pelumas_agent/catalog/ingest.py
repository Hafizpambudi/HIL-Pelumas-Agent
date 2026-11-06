import json
from pathlib import Path

from sqlalchemy.orm import Session

from pelumas_agent.db.models import Equivalence, FitmentRule, Product, Spec

SEED_PATH = Path(__file__).parent / "data" / "products_seed.json"


def product_doc_text(product: Product) -> str:
    parts = [product.name, product.brand, product.category]
    if product.part_no:
        parts.append(product.part_no)
    for alias in product.aliases or []:
        parts.append(str(alias))
    if product.description_id:
        parts.append(product.description_id)
    for spec in product.specs:
        parts.append(f"{spec.key}: {spec.value_text or spec.value_num}")
    return " ".join(str(p) for p in parts)


def load_seed_catalog(
    session: Session, seed_path: Path | str | None = None, embedder=None
) -> int:
    path = Path(seed_path) if seed_path else SEED_PATH
    data = json.loads(path.read_text(encoding="utf-8"))

    session.query(Equivalence).delete()
    session.query(Spec).delete()
    session.query(FitmentRule).delete()
    session.query(Product).delete()
    session.flush()

    products: list[Product] = []
    for raw in data["products"]:
        product = Product(
            part_no=raw.get("part_no"),
            name=raw["name"],
            aliases=raw.get("aliases", []),
            brand=raw["brand"],
            category=raw["category"],
            subcategory=raw.get("subcategory"),
            slug=raw.get("slug"),
            description_id=raw.get("description_id"),
            source_url=raw.get("source_url"),
            data_confidence=raw.get("data_confidence", "medium"),
            status=raw.get("status", "active"),
        )
        session.add(product)
        session.flush()
        products.append(product)
        for spec_raw in raw.get("specs", []):
            session.add(
                Spec(
                    product_id=product.id,
                    key=spec_raw["key"],
                    value_num=spec_raw.get("value_num"),
                    value_text=spec_raw.get("value_text"),
                    unit=spec_raw.get("unit"),
                    source=spec_raw.get("source", "site"),
                    confidence=spec_raw.get("confidence", "medium"),
                )
            )

    for rule_raw in data.get("fitment_rules", []):
        session.add(
            FitmentRule(
                code=rule_raw["code"],
                category=rule_raw["category"],
                dimension=rule_raw["dimension"],
                relation=rule_raw["relation"],
                threshold=rule_raw.get("threshold", {}),
                rationale=rule_raw["rationale"],
                verified_by=rule_raw.get("verified_by"),
            )
        )

    session.flush()

    by_part = {p.part_no: p for p in products if p.part_no}
    for eq_raw in data.get("equivalences", []):
        a = by_part.get(eq_raw["a_part_no"])
        b = by_part.get(eq_raw["b_part_no"])
        if not a or not b:
            continue
        session.add(
            Equivalence(
                a_product_id=a.id,
                b_product_id=b.id,
                relation=eq_raw["relation"],
                differing_dims=eq_raw.get("differing_dims", {}),
                verified_by=eq_raw.get("verified_by"),
                confidence=eq_raw.get("confidence", "low"),
            )
        )

    if embedder is not None:
        docs = [product_doc_text(p) for p in products]
        vectors = embedder.embed(docs)
        for product, vector in zip(products, vectors, strict=True):
            product.embedding = vector

    session.commit()
    return len(products)
