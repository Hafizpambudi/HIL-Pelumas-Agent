from pelumas_agent.fitment.rules import FitmentRequirement, evaluate_fitment


def _bm250(session_factory):
    session = session_factory()
    try:
        from pelumas_agent.retrieval.search import exact_lookup

        hits = exact_lookup(session, "BM250")
        assert len(hits) == 1
        list(hits[0].specs)
        return hits[0]
    finally:
        session.close()


def test_bm250_fit(seeded):
    product = _bm250(seeded)
    req = FitmentRequirement(
        connection_size_in=2.5, system_pressure_bar=8, flow_lpm=500, fluid="jet A1"
    )
    result = evaluate_fitment(product, req)
    assert result.verdict == "fit"
    assert "connection_size_in" in result.checked


def test_bm250_wrong_size(seeded):
    product = _bm250(seeded)
    req = FitmentRequirement(connection_size_in=2.0)
    result = evaluate_fitment(product, req)
    assert result.verdict == "does_not_fit"
    assert result.dimension == "connection_size_in"


def test_bm250_pressure_margin(seeded):
    product = _bm250(seeded)
    req = FitmentRequirement(system_pressure_bar=10.0)
    result = evaluate_fitment(product, req)
    assert result.verdict == "does_not_fit"
    assert result.dimension == "max_pressure_bar"


def test_bm250_flow_above_max(seeded):
    product = _bm250(seeded)
    req = FitmentRequirement(flow_lpm=2000)
    result = evaluate_fitment(product, req)
    assert result.verdict == "does_not_fit"
    assert result.dimension == "flow_range"


def test_bm250_flow_below_min(seeded):
    product = _bm250(seeded)
    req = FitmentRequirement(flow_lpm=50)
    result = evaluate_fitment(product, req)
    assert result.verdict == "needs_confirmation"
    assert result.dimension == "flow_range"


def test_bm250_diesel_is_question_not_yes(seeded):
    product = _bm250(seeded)
    req = FitmentRequirement(fluid="diesel")
    result = evaluate_fitment(product, req)
    assert result.verdict == "does_not_fit"
    assert result.dimension == "fluid"


def test_missing_spec_needs_confirmation(seeded):
    product = _bm250(seeded)
    req = FitmentRequirement(flange_rating="ASA 300")
    result = evaluate_fitment(product, req)
    assert result.verdict in {"needs_confirmation", "does_not_fit"}


def test_evaluation_order_size_first(seeded):
    product = _bm250(seeded)
    req = FitmentRequirement(connection_size_in=4.0, system_pressure_bar=50, flow_lpm=99999)
    result = evaluate_fitment(product, req)
    assert result.dimension == "connection_size_in"


def test_no_requirements(seeded):
    product = _bm250(seeded)
    result = evaluate_fitment(product, FitmentRequirement())
    assert result.verdict == "needs_confirmation"
