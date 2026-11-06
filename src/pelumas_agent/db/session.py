from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from pelumas_agent.config import get_settings
from pelumas_agent.db.models import Base

_engine = None
_SessionLocal = None


def _build_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    eng = create_engine(database_url, connect_args=connect_args)
    if database_url.startswith("sqlite"):

        @event.listens_for(eng, "connect")
        def _fk_on(dbapi_conn, _record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return eng


def engine():
    global _engine
    if _engine is None:
        _engine = _build_engine(get_settings().database_url)
    return _engine


def session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=engine(), expire_on_commit=False)
    return _SessionLocal


def get_session() -> Iterator[Session]:
    factory = session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    eng = engine()
    if eng.dialect.name == "postgresql":
        with eng.connect() as conn:
            conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
            conn.commit()
    Base.metadata.create_all(eng)


def reset_for_tests(database_url: str) -> None:
    global _engine, _SessionLocal
    _engine = _build_engine(database_url)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    Base.metadata.create_all(_engine)
