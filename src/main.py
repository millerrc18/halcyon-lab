import argparse
from src.email.notifier import send_email
from src.journal.store import initialize_database
from src.packets.template import build_demo_packet
from src.universe.sp100 import get_sp100_universe


def cmd_init_db(args):
    initialize_database(args.db_path)
    print(f"Initialized journal database at {args.db_path}")


def cmd_demo_packet(args):
    packet = build_demo_packet()
    print(packet)


def cmd_send_test_email(args):
    subject = "[TRADE DESK] Test Email"
    body = "This is a test from the AI Research Desk. Email delivery is working."
    success = send_email(subject, body)
    if success:
        print("Test email sent successfully.")
    else:
        print("Failed to send test email. Check config and credentials.")


def cmd_ingest(args):
    from src.data_ingestion.market_data import fetch_ohlcv, fetch_spy_benchmark

    universe = get_sp100_universe()
    print(f"Fetching OHLCV data for {len(universe)} tickers + SPY...")

    ohlcv = fetch_ohlcv(universe)
    spy = fetch_spy_benchmark()

    succeeded = len(ohlcv)
    failed = len(universe) - succeeded

    print(f"\nIngestion complete:")
    print(f"  Tickers succeeded: {succeeded}")
    print(f"  Tickers failed:    {failed}")

    if ohlcv:
        sample = next(iter(ohlcv.values()))
        print(f"  Date range:        {sample.index.min().date()} to {sample.index.max().date()}")

    if spy.empty:
        print("  SPY benchmark:     FAILED")
    else:
        print(f"  SPY benchmark:     OK ({len(spy)} rows)")


def cmd_scan(args):
    universe = get_sp100_universe()
    print(f"Universe loaded: {len(universe)} tickers")
    print("Placeholder scan complete. Ranking and packet generation not implemented yet.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI Research Desk MVP skeleton")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_db = subparsers.add_parser("init-db", help="Initialize local SQLite journal")
    init_db.add_argument("--db-path", default="ai_research_desk.sqlite3")
    init_db.set_defaults(func=cmd_init_db)

    demo_packet = subparsers.add_parser("demo-packet", help="Print a demo trade packet")
    demo_packet.set_defaults(func=cmd_demo_packet)

    send_test = subparsers.add_parser("send-test-email", help="Send a test email")
    send_test.set_defaults(func=cmd_send_test_email)

    ingest = subparsers.add_parser("ingest", help="Fetch OHLCV data for S&P 100 universe")
    ingest.set_defaults(func=cmd_ingest)

    scan = subparsers.add_parser("scan", help="Run placeholder universe scan")
    scan.set_defaults(func=cmd_scan)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
