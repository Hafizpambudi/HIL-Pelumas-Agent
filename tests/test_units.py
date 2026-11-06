from pelumas_agent.catalog.units import (
    f_to_c,
    gpm_imp_to_lpm,
    gpm_us_to_lpm,
    m3h_to_lpm,
    parse_size,
    psi_to_bar,
    reconcile_flow,
)


def test_parse_size_fractions():
    assert parse_size("2 1/2") == 2.5
    assert parse_size("2 1/2 Inch") == 2.5
    assert parse_size("2\u00bd") == 2.5
    assert parse_size('2.5"') == 2.5
    assert parse_size("3/4") == 0.75
    assert parse_size("4") == 4.0
    assert parse_size(1.5) == 1.5


def test_parse_size_garbage():
    assert parse_size(None) is None
    assert parse_size("") is None
    assert parse_size("besar") is None


def test_psi_to_bar():
    assert abs(psi_to_bar(150) - 10.3421) < 0.001


def test_f_to_c():
    assert f_to_c(300) == 148.89


def test_gallon_conversions_differ():
    assert gpm_us_to_lpm(100) == 378.54
    assert gpm_imp_to_lpm(100) == 454.61
    assert gpm_imp_to_lpm(100) - gpm_us_to_lpm(100) > 70


def test_m3h_to_lpm():
    assert m3h_to_lpm(68) == 1133.33


def test_reconcile_flow_bm250_consistent():
    assert reconcile_flow(imp_gpm=25, lpm=115, m3h=7) is True
    assert reconcile_flow(imp_gpm=250, lpm=1140, m3h=68) is True


def test_reconcile_flow_us_gallon_assumption_fails():
    assert reconcile_flow(imp_gpm=25, lpm=94.6, m3h=None) is False


def test_reconcile_flow_single_value_ok():
    assert reconcile_flow(imp_gpm=None, lpm=100, m3h=None) is True
