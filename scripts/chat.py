import argparse
import os

from pelumas_agent.config import get_settings
from pelumas_agent.db.models import Product
from pelumas_agent.db.session import init_db, session_factory
from pelumas_agent.llm.embeddings import HashEmbedder, get_embedder
from pelumas_agent.llm.mock import MockLLM
from pelumas_agent.orchestrator.engine import Orchestrator
from pelumas_agent.whatsapp.transport import MockTransport

BUYER_PHONE = "6281200000099"


def main() -> None:
    parser = argparse.ArgumentParser(description="CLI demo chat with the agent")
    parser.add_argument("--mock", action="store_true", help="force MockLLM even if keys exist")
    parser.add_argument(
        "--database-url",
        default=None,
        help="database URL; --mock defaults to local SQLite",
    )
    args = parser.parse_args()

    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    elif args.mock:
        os.environ["DATABASE_URL"] = "sqlite:///./pelumas-demo.db"

    get_settings.cache_clear()
    settings = get_settings()
    init_db()
    factory = session_factory()
    session = factory()
    try:
        count = session.query(Product.id).count()
        embedder = HashEmbedder() if args.mock else get_embedder()
        if count == 0:
            from pelumas_agent.catalog.ingest import load_seed_catalog

            load_seed_catalog(session, embedder=embedder)

        if args.mock or not settings.openai_api_key:
            llm = MockLLM()
            if not settings.openai_api_key:
                print("(OPENAI_API_KEY kosong, pakai MockLLM)")
        else:
            from pelumas_agent.llm.openai_provider import OpenAIClient

            llm = OpenAIClient()
            print(f"(LLM: {settings.openai_model} @ {settings.openai_base_url or 'openai'})")

        transport = MockTransport()
        orchestrator = Orchestrator(
            session=session,
            llm=llm,
            embedder=embedder,
            transport=transport,
            settings=settings,
        )

        print("Demo chat. Ketik pesan sebagai buyer.", flush=True)
        print("Perintah: /admin <pesan>  /state  /new  /quit", flush=True)
        shown = 0
        while True:
            try:
                line = input("buyer> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                continue
            if line == "/quit":
                break
            if line == "/new":
                session.rollback()
                orchestrator = Orchestrator(
                    session=session,
                    llm=llm,
                    embedder=embedder,
                    transport=transport,
                    settings=settings,
                )
                orchestrator._get_or_create_conversation(
                    f"demo-{len(transport.sent)}", BUYER_PHONE
                )
                print("(percakapan baru)")
                continue
            if line == "/state":
                conv = orchestrator._get_or_create_conversation("demo", BUYER_PHONE)
                print(f"stage={conv.stage} buyer_type={conv.buyer_type}")
                print(f"state={conv.state_json}")
                continue

            if line.startswith("/admin "):
                turn = orchestrator.handle_message("demo", settings.admin_numbers[0], line[7:])
                for reply in turn.replies:
                    print(f"agent->admin: {reply}")
                _show_buyer(transport, shown)
                shown = len(transport.sent)
                continue

            turn = orchestrator.handle_message("demo", BUYER_PHONE, line)
            _show_admin(transport, shown, settings)
            for reply in turn.replies:
                print(f"agent> {reply}")
            shown = len(transport.sent)
    finally:
        session.close()


def _show_admin(transport: MockTransport, shown: int, settings) -> None:
    for to, text in transport.sent[shown:]:
        if to in settings.admin_numbers:
            print(f"[admin <- {text}]")


def _show_buyer(transport: MockTransport, shown: int) -> None:
    for to, text in transport.sent[shown:]:
        if to == BUYER_PHONE:
            print(f"agent->buyer: {text}")


if __name__ == "__main__":
    main()
