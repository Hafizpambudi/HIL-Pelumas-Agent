import argparse

from pelumas_agent.db.models import Product
from pelumas_agent.db.session import init_db, session_factory
from pelumas_agent.llm.embeddings import get_embedder


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the catalog database")
    parser.add_argument("--seed", default=None, help="path to seed JSON (default: built-in)")
    args = parser.parse_args()

    init_db()
    factory = session_factory()
    session = factory()
    try:
        from pelumas_agent.catalog.ingest import load_seed_catalog

        count = load_seed_catalog(session, seed_path=args.seed, embedder=get_embedder())
        total_specs = session.query(Product).count()
        print(f"seeded {count} products (table now has {total_specs})")
    finally:
        session.close()


if __name__ == "__main__":
    main()
