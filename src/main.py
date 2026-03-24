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
    from src.config import load_config
    from src.data_ingestion.market_data import fetch_ohlcv, fetch_spy_benchmark
    from src.features.engine import compute_all_features
    from src.journal.store import log_recommendation
    from src.packets.template import build_packet_from_features, render_packet
    from src.ranking.ranker import rank_universe, get_top_candidates

    verbose = getattr(args, "verbose", False)
    dry_run = getattr(args, "dry_run", False)
    send_via_email = getattr(args, "email", False)

    config = load_config()

    # 1. Load universe
    universe = get_sp100_universe()
    if verbose:
        print(f"Universe loaded: {len(universe)} tickers")

    # 2. Fetch OHLCV data
    if verbose:
        print("Fetching OHLCV data...")
    ohlcv = fetch_ohlcv(universe)
    spy = fetch_spy_benchmark()
    if verbose:
        succeeded = len(ohlcv)
        failed = len(universe) - succeeded
        print(f"  Data fetched: {succeeded} succeeded, {failed} failed")
        if spy.empty:
            print("  SPY benchmark: FAILED")
        else:
            print(f"  SPY benchmark: OK ({len(spy)} rows)")

    if spy.empty:
        print("ERROR: Could not fetch SPY benchmark. Aborting scan.")
        return

    # 3. Compute features
    if verbose:
        print("Computing features...")
    features = compute_all_features(ohlcv, spy)
    if verbose:
        print(f"  Features computed for {len(features)} tickers")

    # 4. Rank and qualify
    if verbose:
        print("Ranking universe...")
    ranked = rank_universe(features)
    candidates = get_top_candidates(ranked)

    packet_worthy = candidates["packet_worthy"]
    watchlist = candidates["watchlist"]

    if verbose:
        print(f"  Packet-worthy: {len(packet_worthy)}")
        print(f"  Watchlist:     {len(watchlist)}")
        print()
        if ranked:
            print("Top scores:")
            for r in ranked[:15]:
                feat = r["features"]
                earnings_tag = ""
                if feat.get("event_risk_level") in ("elevated", "imminent"):
                    days = feat.get("days_to_earnings", "?")
                    earnings_tag = f"  [EARNINGS {feat['event_risk_level'].upper()} {days}d]"
                elif feat.get("earnings_date"):
                    earnings_tag = f"  earnings={feat['earnings_date']}"
                print(f"  {r['ticker']:6s}  score={r['score']:5.1f}  {r['qualification']}{earnings_tag}")
            print()

    # 5-6. Generate packets and log
    if not packet_worthy:
        print(f"No packet-worthy setups found today. {len(watchlist)} names on watchlist.")
    else:
        print(f"\n{'='*60}")
        print(f"PACKET-WORTHY NAMES: {len(packet_worthy)}")
        print(f"{'='*60}")

        for candidate in packet_worthy:
            ticker = candidate["ticker"]
            feat = candidate["features"]
            feat["_score"] = candidate["score"]

            if candidate.get("earnings_risk"):
                print(f"  *** {ticker} — EARNINGS RISK PACKET ***")

            packet = build_packet_from_features(ticker, feat, config)
            rendered = render_packet(packet)
            print(rendered)

            if not dry_run:
                rec_id = log_recommendation(
                    packet, feat, candidate["score"], candidate["qualification"]
                )
                print(f"  -> Logged to journal: {rec_id}")

            if send_via_email and not dry_run:
                subject = f"[TRADE DESK] Action Packet - {ticker}"
                success = send_email(subject, rendered)
                if success:
                    print(f"  -> Email sent for {ticker}")
                else:
                    print(f"  -> Failed to send email for {ticker}")

    # Print watchlist summary
    if watchlist:
        print(f"\n{'='*60}")
        print(f"WATCHLIST ({len(watchlist)} names):")
        print(f"{'='*60}")
        for w in watchlist:
            feat = w["features"]
            print(
                f"  {w['ticker']:6s}  score={w['score']:5.1f}  "
                f"trend={feat.get('trend_state', 'n/a')}  "
                f"RS={feat.get('relative_strength_state', 'n/a')}  "
                f"pullback={feat.get('pullback_depth_pct', 0):.1f}%"
            )

    if dry_run:
        print("\n[DRY RUN] No journal entries written, no emails sent.")


def cmd_morning_watchlist(args):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from src.config import load_config
    from src.data_ingestion.market_data import fetch_ohlcv, fetch_spy_benchmark
    from src.features.engine import compute_all_features
    from src.journal.store import log_recommendation
    from src.packets.template import build_packet_from_features, render_packet
    from src.packets.watchlist import build_morning_watchlist
    from src.ranking.ranker import rank_universe, get_top_candidates

    dry_run = getattr(args, "dry_run", False)
    send_via_email = getattr(args, "email", False)

    config = load_config()
    et = ZoneInfo("America/New_York")
    date_str = datetime.now(et).strftime("%Y-%m-%d")

    # Run full scan pipeline
    universe = get_sp100_universe()
    print(f"Running morning scan for {len(universe)} tickers...")

    ohlcv = fetch_ohlcv(universe)
    spy = fetch_spy_benchmark()

    if spy.empty:
        print("ERROR: Could not fetch SPY benchmark. Aborting.")
        return

    features = compute_all_features(ohlcv, spy)
    ranked = rank_universe(features)
    candidates = get_top_candidates(ranked)

    packet_worthy = candidates["packet_worthy"]
    watchlist = candidates["watchlist"]

    # Build and print the watchlist email
    body = build_morning_watchlist(watchlist, packet_worthy, date_str)
    print(body)

    if send_via_email and not dry_run:
        subject = f"[TRADE DESK] Morning Watchlist - {date_str}"
        success = send_email(subject, body)
        if success:
            print("\n  -> Morning watchlist email sent.")
        else:
            print("\n  -> Failed to send morning watchlist email.")

        # Send individual action packet emails for packet-worthy names
        for candidate in packet_worthy:
            ticker = candidate["ticker"]
            feat = candidate["features"]
            feat["_score"] = candidate["score"]

            packet = build_packet_from_features(ticker, feat, config)
            rendered = render_packet(packet)

            rec_id = log_recommendation(
                packet, feat, candidate["score"], candidate["qualification"]
            )
            print(f"  -> Logged {ticker} to journal: {rec_id}")

            pkt_subject = f"[TRADE DESK] Action Packet - {ticker}"
            success = send_email(pkt_subject, rendered)
            if success:
                print(f"  -> Action packet email sent for {ticker}")
            else:
                print(f"  -> Failed to send action packet email for {ticker}")

    if dry_run:
        print("\n[DRY RUN] No journal entries written, no emails sent.")


def cmd_eod_recap(args):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from src.config import load_config
    from src.data_ingestion.market_data import fetch_ohlcv, fetch_spy_benchmark
    from src.features.engine import compute_all_features
    from src.journal.store import get_todays_recommendations
    from src.packets.eod_recap import build_eod_recap
    from src.ranking.ranker import rank_universe, get_top_candidates

    dry_run = getattr(args, "dry_run", False)
    send_via_email = getattr(args, "email", False)

    et = ZoneInfo("America/New_York")
    date_str = datetime.now(et).strftime("%Y-%m-%d")

    # Run full scan pipeline to get current watchlist state
    universe = get_sp100_universe()
    print(f"Running EOD scan for {len(universe)} tickers...")

    ohlcv = fetch_ohlcv(universe)
    spy = fetch_spy_benchmark()

    if spy.empty:
        print("ERROR: Could not fetch SPY benchmark. Aborting.")
        return

    features = compute_all_features(ohlcv, spy)
    ranked = rank_universe(features)
    candidates = get_top_candidates(ranked)

    packet_worthy = candidates["packet_worthy"]
    watchlist = candidates["watchlist"]

    # Query journal for today's entries
    journal_entries = get_todays_recommendations()

    # Build and print the EOD recap
    body = build_eod_recap(packet_worthy, watchlist, journal_entries, date_str)
    print(body)

    if send_via_email and not dry_run:
        subject = f"[TRADE DESK] EOD Recap - {date_str}"
        success = send_email(subject, body)
        if success:
            print("\n  -> EOD recap email sent.")
        else:
            print("\n  -> Failed to send EOD recap email.")

    if dry_run:
        print("\n[DRY RUN] No emails sent.")


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

    scan = subparsers.add_parser("scan", help="Run full scan pipeline")
    scan.add_argument("--verbose", action="store_true", help="Print intermediate steps")
    scan.add_argument("--email", action="store_true", help="Send packets via email")
    scan.add_argument("--dry-run", action="store_true", help="Run pipeline without writing journal or sending email")
    scan.set_defaults(func=cmd_scan)

    mw = subparsers.add_parser("morning-watchlist", help="Generate and send morning watchlist")
    mw.add_argument("--email", action="store_true", help="Send watchlist and action packets via email")
    mw.add_argument("--dry-run", action="store_true", help="Print only, no email or journal writes")
    mw.set_defaults(func=cmd_morning_watchlist)

    eod = subparsers.add_parser("eod-recap", help="Generate and send EOD recap")
    eod.add_argument("--email", action="store_true", help="Send EOD recap via email")
    eod.add_argument("--dry-run", action="store_true", help="Print only, no email")
    eod.set_defaults(func=cmd_eod_recap)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
