import pytest

from pelumas_agent.config import get_settings

ADMIN_PHONE = "6281200000001"
BUYER_PHONE = "6281200000099"


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("ADMIN_NUMBERS", ADMIN_PHONE)
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("AVAILABILITY_MODE", "manual")
    get_settings.cache_clear()

    from pelumas_agent.db import session as db_session

    db_session.reset_for_tests(get_settings().database_url)
    yield db_session.session_factory()

    db_session._engine = None
    db_session._SessionLocal = None
    get_settings.cache_clear()


@pytest.fixture
def seeded(db):
    from pelumas_agent.catalog.ingest import load_seed_catalog
    from pelumas_agent.llm.embeddings import HashEmbedder

    session = db()
    try:
        load_seed_catalog(session, embedder=HashEmbedder(dim=256))
    finally:
        session.close()
    return db
