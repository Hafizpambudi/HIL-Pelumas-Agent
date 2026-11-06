from pelumas_agent.llm.embeddings import HashEmbedder
from pelumas_agent.retrieval.search import (
    exact_lookup,
    filtered_lookup,
    search_tiered,
    semantic_lookup,
)


def test_exact_part_number(seeded):
    session = seeded()
    try:
        hits = exact_lookup(session, "BM250")
        assert [p.part_no for p in hits] == ["BM250"]
    finally:
        session.close()


def test_exact_case_insensitive(seeded):
    session = seeded()
    try:
        assert exact_lookup(session, "bm250")[0].part_no == "BM250"
        assert exact_lookup(session, "husky-1050")[0].brand == "Graco"
    finally:
        session.close()


def test_fuzzy_misspelling_brand_model(seeded):
    session = seeded()
    try:
        hits = exact_lookup(session, "avery bm 250")
        assert len(hits) == 1
        assert hits[0].part_no == "BM250"
    finally:
        session.close()


def test_site_typo_alias_resolves(seeded):
    session = seeded()
    try:
        hits = exact_lookup(session, "husky automatic heavy nozle")
        assert len(hits) == 1
        assert hits[0].brand == "Husky"
    finally:
        session.close()


def test_filtered_diesel_one_inch(seeded):
    session = seeded()
    try:
        hits = filtered_lookup(
            session, category="flow_meter", fluid="diesel", connection_size_in=1.0
        )
        part_nos = {p.part_no for p in hits}
        assert "F100" in part_nos
        assert "BM250" not in part_nos
    finally:
        session.close()


def test_filtered_flow_range(seeded):
    session = seeded()
    try:
        hits = filtered_lookup(session, category="flow_meter", fluid="diesel", flow_lpm=500)
        part_nos = {p.part_no for p in hits}
        assert "M7" in part_nos or "FHF-3010" in part_nos
        assert "F100" not in part_nos
    finally:
        session.close()


def test_semantic_returns_candidates(seeded):
    session = seeded()
    try:
        embedder = HashEmbedder(dim=256)
        results = semantic_lookup(session, "meteran bahan bakar diesel", embedder)
        assert len(results) > 0
    finally:
        session.close()


def test_tier_precedence_exact_first(seeded):
    session = seeded()
    try:
        tier, products = search_tiered(session, "BM250", embedder=HashEmbedder(dim=256))
        assert tier == "exact"
        assert products[0].part_no == "BM250"
    finally:
        session.close()


def test_tier_filtered_when_filters_given(seeded):
    session = seeded()
    try:
        tier, products = search_tiered(
            session, "cari meter", embedder=HashEmbedder(dim=256),
            category="flow_meter", fluid="diesel", connection_size_in=1.0,
        )
        assert tier == "filtered"
        assert products
    finally:
        session.close()


def test_tier_semantic_fallback(seeded):
    session = seeded()
    try:
        tier, _ = search_tiered(
            session, "butuh alat ukur aliran bahan bakar", embedder=HashEmbedder(dim=256)
        )
        assert tier in {"semantic", "none"}
    finally:
        session.close()


def test_discontinued_excluded_from_filtered(seeded):
    session = seeded()
    try:
        from pelumas_agent.db.models import Product

        product = session.query(Product).filter(Product.part_no == "F100").first()
        product.status = "discontinued"
        session.commit()
        hits = filtered_lookup(session, category="flow_meter", fluid="diesel")
        assert "F100" not in {p.part_no for p in hits}
        hits = filtered_lookup(session, fluid="diesel", include_discontinued=True)
        assert "F100" in {p.part_no for p in hits}
    finally:
        session.close()
