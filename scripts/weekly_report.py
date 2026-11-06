import argparse

from pelumas_agent.db.session import init_db, session_factory
from pelumas_agent.reporting.weekly import weekly_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Weekly demand report")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    init_db()
    factory = session_factory()
    session = factory()
    try:
        report = weekly_report(session, days=args.days)
    finally:
        session.close()

    print(f"Window: {report['window_days']} hari")
    print(f"Percakapan: {report['conversations']}")
    print(f"RFQ dibuat: {report['rfqs']}")
    print(f"RFQ diberi harga: {report['rfqs_priced']}")
    print(f"Konversi percakapan -> RFQ: {report['conversion']:.0%}")
    print(f"Guard blocks: {report['guard_blocks']}")
    print(f"Handoffs: {report['handoffs']}")
    if report["handoff_reasons"]:
        for reason, count in report["handoff_reasons"].items():
            print(f"  - {reason}: {count}")
    print("Part paling diminta:")
    for part, count in report["top_requested_parts"]:
        print(f"  - {part}: {count}")


if __name__ == "__main__":
    main()
