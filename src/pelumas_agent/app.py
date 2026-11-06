from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import func

from pelumas_agent.config import Settings, get_settings
from pelumas_agent.db.models import Product
from pelumas_agent.db.session import init_db, session_factory
from pelumas_agent.handoff import sweep_pending_handoffs
from pelumas_agent.llm.embeddings import get_embedder
from pelumas_agent.orchestrator.engine import Orchestrator
from pelumas_agent.whatsapp.webhook import make_router


def create_app(
    settings: Settings | None = None,
    llm=None,
    transport=None,
    embedder=None,
    adapter=None,
) -> FastAPI:
    settings = settings or get_settings()
    embedder = embedder or get_embedder()

    if llm is None:
        if settings.openai_api_key:
            from pelumas_agent.llm.openai_provider import OpenAIClient

            llm = OpenAIClient()
        else:
            from pelumas_agent.llm.mock import MockLLM

            llm = MockLLM()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        import asyncio

        init_db()
        factory = session_factory()
        session = factory()
        try:
            count = session.query(func.count(Product.id)).scalar() or 0
            if count == 0:
                from pelumas_agent.catalog.ingest import load_seed_catalog

                load_seed_catalog(session, embedder=embedder)
        finally:
            session.close()

        sweep_task = None
        if settings.handoff_sweep_enabled:

            async def sweep_loop():
                while True:
                    await asyncio.sleep(settings.handoff_sweep_seconds)
                    sweep_session = session_factory()()
                    try:
                        sweep_pending_handoffs(sweep_session, settings, transport)
                    except Exception:
                        sweep_session.rollback()
                    finally:
                        sweep_session.close()

            sweep_task = asyncio.create_task(sweep_loop())

        try:
            yield
        finally:
            if sweep_task is not None:
                sweep_task.cancel()

    app = FastAPI(title="pelumas-agent", version="0.1.0", lifespan=lifespan)

    def orchestrator_factory(session) -> Orchestrator:
        return Orchestrator(
            session=session,
            llm=llm,
            embedder=embedder,
            adapter=adapter,
            transport=transport,
            settings=settings,
        )

    app.include_router(make_router(orchestrator_factory, settings))

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/rfq/{rfq_id}")
    def rfq_view(rfq_id: str):
        from pelumas_agent.rfq.service import RfqService

        factory = session_factory()
        session = factory()
        try:
            rfq = RfqService(session).get(rfq_id)
            if rfq is None:
                return {"error": "not found"}
            return {
                "id": rfq.id,
                "status": rfq.status,
                "buyer_type": rfq.buyer_type,
                "company": rfq.company,
                "items": rfq.items,
                "delivery_city": rfq.delivery_city,
                "urgency": rfq.urgency,
                "open_questions": rfq.open_questions,
                "quoted_total": rfq.quoted_total,
                "quoted_by": rfq.quoted_by,
                "quoted_at": rfq.quoted_at.isoformat() if rfq.quoted_at else None,
            }
        finally:
            session.close()

    return app


app = None


def get_app() -> FastAPI:
    global app
    if app is None:
        app = create_app()
    return app
