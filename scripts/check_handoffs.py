import argparse
import json
import os

from pelumas_agent.config import get_settings
from pelumas_agent.db.session import init_db, session_factory
from pelumas_agent.handoff import sweep_pending_handoffs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="One-shot sweep: notify buyers whose RFQ has no admin reply yet"
    )
    parser.add_argument("--dry-run", action="store_true", help="list matches, send nothing")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--database-url", default=None, help="override DATABASE_URL")
    args = parser.parse_args()

    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
        get_settings.cache_clear()

    settings = get_settings()

    try:
        init_db()
    except Exception as error:
        print(f"database unreachable at {settings.database_url}: {error}")
        print("hint: docker compose up -d db, or pass --database-url sqlite:///./pelumas.db")
        raise SystemExit(2) from error
    session = session_factory()()
    try:
        from pelumas_agent.whatsapp.transport import WhatsAppCloudTransport

        transport = None
        if not args.dry_run and settings.wa_access_token:
            transport = WhatsAppCloudTransport(settings)

        results = sweep_pending_handoffs(
            session, settings, transport, dry_run=args.dry_run
        )
    finally:
        session.close()

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    label = "would notify" if args.dry_run else "notified"
    print(f"{len(results)} overdue handoff(s); {label}")
    for row in results:
        print(f"- {row['rfq_id']} · stage={row['stage']} · {row['buyer_phone']}")


if __name__ == "__main__":
    main()
