import json
import re
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parent.parent / "site"
ASSETS = SITE / "assets"


@pytest.fixture(scope="module")
def i18n():
    return json.loads((ASSETS / "i18n.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def transcripts():
    return json.loads((ASSETS / "transcripts.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def demos_html():
    return (SITE / "demo.html").read_text(encoding="utf-8")


def test_both_languages_present(i18n):
    assert set(i18n) == {"id", "en"}


def test_key_parity(i18n):
    assert set(i18n["id"]) == set(i18n["en"])


def test_no_empty_translations(i18n):
    for lang, table in i18n.items():
        for key, value in table.items():
            assert value.strip(), f"{lang}.{key} is empty"


def _used_keys(demos_html: str) -> set[str]:
    keys = set(re.findall(r'data-i18n="([^"]+)"', demos_html))
    for raw in re.findall(r'data-i18n-attr="([^"]+)"', demos_html):
        for pair in raw.split(";"):
            _, key = pair.split(":")
            keys.add(key)
    return keys


def test_all_html_keys_defined(demos_html, i18n):
    missing = _used_keys(demos_html) - set(i18n["id"])
    assert not missing, f"undefined i18n keys: {sorted(missing)}"


def test_no_orphan_keys(demos_html, i18n, ):
    js = (ASSETS / "demo.js").read_text(encoding="utf-8")
    used = _used_keys(demos_html) | set(re.findall(r't\("([a-z][\w.]*)"', js))
    declared = set(i18n["id"])
    dynamic = {
        "buyerType.engineer",
        "buyerType.procurement",
        "buyerType.project",
        "buyerType.unknown",
        "status.ready",
        "status.sent_to_admin",
        "status.priced",
        "status.closed",
        "status.lost",
    }
    orphans = declared - used - dynamic
    assert not orphans, f"unused i18n keys: {sorted(orphans)}"


def test_scenario_translations_complete(transcripts):
    for scenario in transcripts["scenarios"]:
        assert scenario.get("title_en"), f"{scenario['id']} missing title_en"
        assert scenario.get("subtitle_en"), f"{scenario['id']} missing subtitle_en"


def test_message_translations_aligned(transcripts):
    for scenario in transcripts["scenarios"]:
        for index, message in enumerate(scenario["messages"]):
            where = f"{scenario['id']}#{index}"
            if message["role"] == "trace":
                assert "text_en" not in message, f"{where} trace must not carry text_en"
            else:
                assert message.get("text_en"), f"{where} missing text_en"


def test_guard_proof_translations(transcripts):
    for proof in transcripts["guard_proofs"]:
        assert proof.get("attempt_en"), f"{proof['rule']} missing attempt_en"
        assert "replacement_en" in proof


def test_catalog_and_model_translated(transcripts):
    assert transcripts.get("catalog_en")
    assert transcripts.get("model_en")


def test_language_switch_markup(demos_html):
    assert 'data-lang="id"' in demos_html
    assert 'data-lang="en"' in demos_html
    assert demos_html.count('class="lang-btn"') == 2
    assert 'aria-pressed' in demos_html


def test_no_hardcoded_indonesian_in_js():
    js = (ASSETS / "demo.js").read_text(encoding="utf-8")
    for banned in ('"Putar"', '"Jeda"', '"Pembeli"', '"Langkah"', '"Ulang"'):
        assert banned not in js, f"hardcoded string {banned} still in demo.js"
