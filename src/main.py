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
    from src.llm.packet_writer import enhance_packet_with_llm
    from src.packets.template import build_packet_from_features, render_packet
    from src.ranking.ranker import rank_universe, get_top_candidates

    verbose = getattr(args, "verbose", False)
    dry_run = getattr(args, "dry_run", False)
    send_via_email = getattr(args, "email", False)
    no_shadow = getattr(args, "no_shadow", False)

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
    shadow_cfg = config.get("shadow_trading", {})
    shadow_enabled = shadow_cfg.get("enabled", False) and not no_shadow and not dry_run
    trades_opened = 0
    trades_closed = 0

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
            packet = enhance_packet_with_llm(packet, feat, config)
            rendered = render_packet(packet)
            print(rendered)

            rec_id = None
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

            # Open shadow trade
            if shadow_enabled and rec_id:
                from src.shadow_trading.executor import open_shadow_trade
                trade_id = open_shadow_trade(rec_id, packet, feat)
                if trade_id:
                    trades_opened += 1

    # Check and manage existing open trades
    if shadow_enabled:
        from src.shadow_trading.executor import check_and_manage_open_trades
        actions = check_and_manage_open_trades()
        trades_closed = len([a for a in actions if a["type"] == "closed"])

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

    # Print shadow status if enabled
    if shadow_enabled and verbose:
        from src.journal.store import get_open_shadow_trades
        open_trades = get_open_shadow_trades()
        print(f"\nSHADOW LEDGER STATUS:")
        print(f"  Open trades: {len(open_trades)}")
        print(f"  Trades opened this scan: {trades_opened}")
        print(f"  Trades closed this scan: {trades_closed}")
        if open_trades:
            print(f"\n  Open positions:")
            for t in open_trades:
                entry = t.get("actual_entry_price") or t.get("entry_price", 0)
                days = t.get("duration_days", 0) or 0
                timeout = shadow_cfg.get("timeout_days", 15)
                # Try to get current price for display
                from src.shadow_trading.executor import _get_current_price_safe
                current = _get_current_price_safe(t["ticker"])
                if current and entry > 0:
                    pnl = current - entry
                    pnl_pct = pnl / entry * 100
                    print(
                        f"    {t['ticker']:6s}  entry=${entry:.2f}  current=${current:.2f}  "
                        f"P&L=${pnl:+.2f} ({pnl_pct:+.1f}%)  day {days}/{timeout}"
                    )
                else:
                    print(f"    {t['ticker']:6s}  entry=${entry:.2f}  day {days}/{timeout}")

    if dry_run:
        print("\n[DRY RUN] No journal entries written, no emails sent.")


def cmd_morning_watchlist(args):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from src.config import load_config
    from src.data_ingestion.market_data import fetch_ohlcv, fetch_spy_benchmark
    from src.features.engine import compute_all_features
    from src.journal.store import log_recommendation
    from src.llm.packet_writer import enhance_packet_with_llm
    from src.llm.watchlist_writer import generate_watchlist_narrative
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

    # Generate LLM narrative for the watchlist (if available)
    narrative = generate_watchlist_narrative(packet_worthy, watchlist, config)

    # Build and print the watchlist email
    body = build_morning_watchlist(watchlist, packet_worthy, date_str,
                                  narrative=narrative)
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
            packet = enhance_packet_with_llm(packet, feat, config)
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

    # Get shadow data if shadow trading is enabled
    shadow_data = None
    config = load_config()
    if config.get("shadow_trading", {}).get("enabled", False):
        from src.packets.eod_recap import get_shadow_data_for_recap
        shadow_data = get_shadow_data_for_recap()

    # Build and print the EOD recap
    body = build_eod_recap(packet_worthy, watchlist, journal_entries, date_str, shadow_data=shadow_data)
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


# ── Shadow Ledger CLI Commands ────────────────────────────────────────


def cmd_shadow_status(args):
    from src.journal.store import get_open_shadow_trades
    from src.shadow_trading.executor import _get_current_price_safe
    from src.config import load_config

    config = load_config()
    timeout = config.get("shadow_trading", {}).get("timeout_days", 15)

    open_trades = get_open_shadow_trades()

    if not open_trades:
        print("SHADOW LEDGER — No open trades.")
        return

    print(f"\nSHADOW LEDGER — OPEN TRADES ({len(open_trades)}):")
    print(f"  {'TICKER':6s}  {'ENTRY':>10s}  {'CURRENT':>10s}  {'P&L':>15s}  {'DAYS':>6s}  {'MFE':>8s}  {'MAE':>8s}  {'STOP':>8s}  {'TGT1':>9s}  {'TGT2':>9s}")

    for t in open_trades:
        entry = t.get("actual_entry_price") or t.get("entry_price", 0)
        stop = t.get("stop_price", 0)
        tgt1 = t.get("target_1", 0)
        tgt2 = t.get("target_2", 0)
        days = t.get("duration_days", 0) or 0
        mfe = t.get("max_favorable_excursion", 0) or 0
        mae = t.get("max_adverse_excursion", 0) or 0

        current = _get_current_price_safe(t["ticker"])
        if current and entry > 0:
            pnl = current - entry
            pnl_pct = pnl / entry * 100
            pnl_str = f"${pnl:+.2f} {pnl_pct:+.1f}%"
            current_str = f"${current:.2f}"
        else:
            pnl_str = "n/a"
            current_str = "n/a"

        print(
            f"  {t['ticker']:6s}  ${entry:>9.2f}  {current_str:>10s}  {pnl_str:>15s}  "
            f"{days:>3d}/{timeout:<2d}  ${mfe:>+7.2f}  ${mae:>+7.2f}  "
            f"${stop:>7.2f}  ${tgt1:>8.2f}  ${tgt2:>8.2f}"
        )

    # Account summary
    try:
        from src.shadow_trading.alpaca_adapter import get_account_info
        acct = get_account_info()
        print(
            f"\n  Account: ${acct['equity']:.2f} equity | "
            f"${acct['buying_power']:.2f} buying power | "
            f"{len(open_trades)} open positions"
        )
    except Exception:
        print(f"\n  Account: (unable to connect to Alpaca) | {len(open_trades)} open positions")


def cmd_shadow_history(args):
    from src.journal.store import get_closed_shadow_trades
    from src.shadow_trading.metrics import compute_shadow_metrics

    days = getattr(args, "days", 30)
    closed = get_closed_shadow_trades(days=days)

    if not closed:
        print(f"SHADOW LEDGER — No closed trades in the last {days} days.")
        return

    print(f"\nSHADOW LEDGER — CLOSED TRADES (last {days} days):")
    print(f"  {'TICKER':6s}  {'ENTRY':>10s}  {'EXIT':>10s}  {'P&L':>15s}  {'DAYS':>5s}  {'EXIT REASON':>15s}  {'MFE':>8s}  {'MAE':>8s}")

    for t in closed:
        entry = t.get("actual_entry_price") or t.get("entry_price", 0)
        exit_p = t.get("actual_exit_price", 0) or 0
        pnl = t.get("pnl_dollars", 0) or 0
        pnl_pct = t.get("pnl_pct", 0) or 0
        days_held = t.get("duration_days", 0) or 0
        reason = t.get("exit_reason", "unknown")
        mfe = t.get("max_favorable_excursion", 0) or 0
        mae = t.get("max_adverse_excursion", 0) or 0

        print(
            f"  {t['ticker']:6s}  ${entry:>9.2f}  ${exit_p:>9.2f}  "
            f"${pnl:>+7.2f} {pnl_pct:>+5.1f}%  {days_held:>5d}  "
            f"{reason:>15s}  ${mfe:>+7.2f}  ${mae:>+7.2f}"
        )

    # Summary
    metrics = compute_shadow_metrics(closed)
    print(
        f"\n  Summary: {metrics['total_trades']} trades | "
        f"{metrics['win_rate']:.0f}% win rate | "
        f"avg gain ${metrics['avg_gain']:.2f} | "
        f"avg loss ${metrics['avg_loss']:.2f} | "
        f"expectancy ${metrics['expectancy']:+.2f}"
    )


def cmd_shadow_close(args):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from src.journal.store import (
        get_open_shadow_trades,
        close_shadow_trade,
        update_recommendation,
        update_shadow_trade,
    )
    from src.shadow_trading.executor import _get_current_price_safe

    ticker = args.ticker.upper()
    reason = getattr(args, "reason", "manual")

    open_trades = get_open_shadow_trades()
    trade = None
    for t in open_trades:
        if t["ticker"] == ticker:
            trade = t
            break

    if not trade:
        print(f"No open shadow trade found for {ticker}.")
        return

    entry = trade.get("actual_entry_price") or trade.get("entry_price", 0)
    current = _get_current_price_safe(ticker) or entry

    pnl_dollars = (current - entry) * (trade.get("planned_shares", 1))
    pnl_pct = ((current - entry) / entry * 100) if entry > 0 else 0

    et = ZoneInfo("America/New_York")
    now = datetime.now(et)

    # Try Alpaca sell
    try:
        from src.shadow_trading.alpaca_adapter import place_paper_exit
        place_paper_exit(ticker, trade.get("planned_shares", 1))
    except Exception as e:
        print(f"Note: Alpaca sell order failed: {e}")

    entry_time_str = trade.get("actual_entry_time") or trade.get("created_at", "")
    try:
        entry_time = datetime.fromisoformat(entry_time_str)
        days_held = (now - entry_time).days
    except (ValueError, TypeError):
        days_held = 0

    close_shadow_trade(
        trade["trade_id"],
        exit_price=current,
        exit_time=now.isoformat(),
        exit_reason=reason,
        pnl_dollars=round(pnl_dollars, 2),
        pnl_pct=round(pnl_pct, 2),
    )

    update_shadow_trade(trade["trade_id"], {"duration_days": days_held})

    # Update journal
    rec_id = trade.get("recommendation_id")
    if rec_id:
        update_recommendation(rec_id, {
            "shadow_exit_price": current,
            "shadow_exit_time": now.isoformat(),
            "shadow_pnl_dollars": round(pnl_dollars, 2),
            "shadow_pnl_pct": round(pnl_pct, 2),
            "shadow_duration_days": days_held,
            "thesis_success": 1 if pnl_dollars > 0 else 0,
        })

    print(
        f"Closed shadow trade for {ticker}: {reason} | "
        f"P&L=${pnl_dollars:+.2f} ({pnl_pct:+.1f}%) | held {days_held} days"
    )


def cmd_shadow_account(args):
    try:
        from src.shadow_trading.alpaca_adapter import get_account_info, get_all_positions
        acct = get_account_info()

        print("\nALPACA PAPER ACCOUNT:")
        print(f"  Status:          {acct['status']}")
        print(f"  Equity:          ${acct['equity']:.2f}")
        print(f"  Cash:            ${acct['cash']:.2f}")
        print(f"  Buying Power:    ${acct['buying_power']:.2f}")
        print(f"  Portfolio Value:  ${acct['portfolio_value']:.2f}")

        positions = get_all_positions()
        if positions:
            print(f"\n  Open Positions ({len(positions)}):")
            for p in positions:
                print(
                    f"    {p['symbol']:6s}  qty={p['qty']}  "
                    f"avg_entry=${p['avg_entry_price']:.2f}  "
                    f"current=${p['current_price']:.2f}  "
                    f"P&L=${p['unrealized_pl']:+.2f}"
                )
        else:
            print("\n  No open positions.")

    except Exception as e:
        print(f"Failed to connect to Alpaca paper account: {e}")
        print("Check your alpaca config in settings.local.yaml or environment variables.")


# ── Review & Evaluation CLI Commands (Sprint 4) ──────────────────────


def cmd_review(args):
    from src.journal.store import (
        get_recommendations_pending_review,
        get_recommendation_by_id,
        update_recommendation_review,
        get_shadow_trade,
    )

    sub = getattr(args, "review_sub", None)

    if sub == "list" or not sub:
        pending = get_recommendations_pending_review()
        if not pending:
            print("No trades pending review.")
            return

        print(f"\nTRADES PENDING REVIEW ({len(pending)}):")
        print(f"  {'ID':36s}  {'TICKER':6s}  {'DATE':12s}  {'ENTRY':>10s}  {'P&L':>10s}")
        for r in pending:
            rec_id = r["recommendation_id"]
            ticker = r.get("ticker", "???")
            date = r.get("created_at", "")[:10]
            entry = r.get("entry_zone", "n/a")
            pnl = r.get("shadow_pnl_dollars")
            pnl_str = f"${pnl:+.2f}" if pnl is not None else "n/a"
            print(f"  {rec_id}  {ticker:6s}  {date:12s}  {entry:>10s}  {pnl_str:>10s}")
        return

    # Review a specific recommendation
    rec_id = sub
    rec = get_recommendation_by_id(rec_id)
    if not rec:
        print(f"Recommendation {rec_id} not found.")
        return

    # Display info
    print(f"\n{'='*60}")
    print(f"REVIEW: {rec['ticker']} — {rec.get('company_name', '')}")
    print(f"{'='*60}")
    print(f"  Date:       {rec.get('created_at', '')[:10]}")
    print(f"  Entry Zone: {rec.get('entry_zone', 'n/a')}")
    print(f"  Stop:       {rec.get('stop_level', 'n/a')}")
    print(f"  Target 1:   {rec.get('target_1', 'n/a')}")
    print(f"  Target 2:   {rec.get('target_2', 'n/a')}")
    print(f"  Confidence: {rec.get('confidence_score', 'n/a')}/10")
    print(f"  Thesis:     {(rec.get('thesis_text') or 'n/a')[:200]}")

    # Shadow outcome
    if rec.get("shadow_pnl_dollars") is not None:
        print(f"\n  Shadow Outcome:")
        print(f"    Entry:    ${rec.get('shadow_entry_price', 0):.2f}")
        print(f"    Exit:     ${rec.get('shadow_exit_price', 0):.2f}")
        print(f"    P&L:      ${rec['shadow_pnl_dollars']:+.2f} ({rec.get('shadow_pnl_pct', 0):+.1f}%)")
        print(f"    Duration: {rec.get('shadow_duration_days', 'n/a')} days")
        print(f"    MFE:      ${rec.get('max_favorable_excursion', 0) or 0:+.2f}")
        print(f"    MAE:      ${rec.get('max_adverse_excursion', 0) or 0:+.2f}")

    # Postmortem
    if rec.get("assistant_postmortem"):
        print(f"\n  Assistant Postmortem:")
        print(f"    {rec['assistant_postmortem'][:500]}")

    # Prompt for review
    print(f"\n--- Review Inputs ---")
    try:
        approved = input("  Did you approve this trade? (y/n): ").strip().lower()
        executed = input("  Did you execute this trade? (y/n): ").strip().lower()
        grade = input("  Grade (A/B/C/D/F): ").strip().upper()
        notes = input("  Notes (optional): ").strip()
        repeatable = input("  Would you take this setup again? (y/n/maybe): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nReview cancelled.")
        return

    review_data = {
        "ryan_approved": 1 if approved == "y" else 0,
        "ryan_executed": 1 if executed == "y" else 0,
        "user_grade": grade if grade in ("A", "B", "C", "D", "F") else None,
        "ryan_notes": notes if notes else None,
        "repeatable_setup": 1 if repeatable == "y" else (0 if repeatable == "n" else None),
    }

    update_recommendation_review(rec_id, review_data)
    print(f"\nReview saved for {rec['ticker']} ({rec_id}).")


def cmd_mark_executed(args):
    from src.journal.store import get_recommendations_by_ticker, update_recommendation

    ticker = args.ticker.upper()
    recs = get_recommendations_by_ticker(ticker, limit=1)

    if not recs:
        print(f"No recommendations found for {ticker}.")
        return

    rec = recs[0]
    update_recommendation(rec["recommendation_id"], {"ryan_executed": 1})
    print(
        f"Marked {ticker} recommendation ({rec['recommendation_id']}) as executed by Ryan."
    )


def cmd_review_scorecard(args):
    from src.evaluation.scorecard import generate_weekly_scorecard

    weeks = getattr(args, "weeks", 1)
    send_via_email = getattr(args, "email", False)

    scorecard = generate_weekly_scorecard(weeks_back=weeks)
    print(scorecard)

    if send_via_email:
        subject = f"[TRADE DESK] Weekly Scorecard"
        success = send_email(subject, scorecard)
        if success:
            print("\n  -> Scorecard email sent.")
        else:
            print("\n  -> Failed to send scorecard email.")


def cmd_review_bootcamp(args):
    from src.evaluation.scorecard import generate_bootcamp_scorecard

    days = getattr(args, "days", 30)
    send_via_email = getattr(args, "email", False)

    scorecard = generate_bootcamp_scorecard(days=days)
    print(scorecard)

    if send_via_email:
        subject = f"[TRADE DESK] Bootcamp Report"
        success = send_email(subject, scorecard)
        if success:
            print("\n  -> Bootcamp report email sent.")
        else:
            print("\n  -> Failed to send bootcamp report email.")


def cmd_postmortems(args):
    from src.journal.store import get_closed_shadow_trades, get_recommendation_by_id

    limit = getattr(args, "limit", 10)
    ticker_filter = getattr(args, "ticker", None)

    closed = get_closed_shadow_trades(days=90)

    if ticker_filter:
        closed = [t for t in closed if t["ticker"] == ticker_filter.upper()]

    closed = closed[:limit]

    if not closed:
        print("No postmortems available.")
        return

    print(f"\nRECENT POSTMORTEMS:")
    print(f"  {'TICKER':6s}  {'DATE':12s}  {'EXIT REASON':>15s}  {'P&L':>10s}  {'LESSON':>20s}  POSTMORTEM")

    for t in closed:
        rec_id = t.get("recommendation_id")
        rec = get_recommendation_by_id(rec_id) if rec_id else None

        ticker = t["ticker"]
        date = (t.get("actual_exit_time") or t.get("created_at", ""))[:10]
        reason = t.get("exit_reason", "unknown")
        pnl = t.get("pnl_dollars", 0) or 0
        pnl_str = f"${pnl:+.2f}"
        lesson = (rec.get("lesson_tag") or "n/a") if rec else "n/a"
        postmortem = (rec.get("assistant_postmortem") or "n/a") if rec else "n/a"
        first_line = postmortem.split("\n")[0][:60] if postmortem != "n/a" else "n/a"

        print(f"  {ticker:6s}  {date:12s}  {reason:>15s}  {pnl_str:>10s}  {lesson:>20s}  {first_line}")

    if rec_id:
        print(f"\n  Use 'postmortem <recommendation_id>' to view full details.")


def cmd_postmortem_detail(args):
    from src.journal.store import get_recommendation_by_id, get_shadow_trade

    rec_id = args.recommendation_id
    rec = get_recommendation_by_id(rec_id)

    if not rec:
        print(f"Recommendation {rec_id} not found.")
        return

    print(f"\n{'='*60}")
    print(f"POSTMORTEM: {rec['ticker']} — {rec.get('company_name', '')}")
    print(f"{'='*60}")

    # Original packet brief
    print(f"\n  Original Packet:")
    print(f"    Entry Zone: {rec.get('entry_zone', 'n/a')}")
    print(f"    Stop:       {rec.get('stop_level', 'n/a')}")
    print(f"    Target 1:   {rec.get('target_1', 'n/a')}")
    print(f"    Target 2:   {rec.get('target_2', 'n/a')}")
    print(f"    Confidence: {rec.get('confidence_score', 'n/a')}/10")

    # Shadow trade details
    if rec.get("shadow_entry_price") is not None:
        print(f"\n  Shadow Trade:")
        print(f"    Entry:    ${rec.get('shadow_entry_price', 0):.2f} on {(rec.get('shadow_entry_time') or '')[:10]}")
        if rec.get("shadow_exit_price") is not None:
            print(f"    Exit:     ${rec.get('shadow_exit_price', 0):.2f} on {(rec.get('shadow_exit_time') or '')[:10]}")
            print(f"    P&L:      ${rec.get('shadow_pnl_dollars', 0):+.2f} ({rec.get('shadow_pnl_pct', 0):+.1f}%)")
            print(f"    Duration: {rec.get('shadow_duration_days', 'n/a')} days")
        print(f"    MFE:      ${rec.get('max_favorable_excursion', 0) or 0:+.2f}")
        print(f"    MAE:      ${rec.get('max_adverse_excursion', 0) or 0:+.2f}")

    # Full postmortem
    postmortem = rec.get("assistant_postmortem")
    if postmortem:
        print(f"\n{postmortem}")
    else:
        print(f"\n  No postmortem generated yet.")

    # Ryan's review
    if rec.get("user_grade"):
        print(f"\n  Ryan's Review:")
        print(f"    Grade:      {rec.get('user_grade')}")
        print(f"    Notes:      {rec.get('ryan_notes') or 'none'}")
        print(f"    Repeatable: {'Yes' if rec.get('repeatable_setup') == 1 else 'No' if rec.get('repeatable_setup') == 0 else 'n/a'}")


def cmd_watch(args):
    from src.config import load_config
    from src.scheduler.watch import WatchLoop

    config = load_config()
    email_mode = getattr(args, "email_mode", None)
    loop = WatchLoop(config, email_mode=email_mode)
    loop.run()


def cmd_preflight(args):
    from src.config import load_config
    from src.llm.client import is_llm_available, generate

    config = load_config()

    print("")
    print("HALCYON LAB - PREFLIGHT CHECK")
    print("=" * 30)

    # 1. Config
    if config:
        print("Config:           [OK] settings.local.yaml loaded")
    else:
        print("Config:           [FAIL] No config file found")

    # 2. Email
    email_cfg = config.get("email", {})
    smtp_ok = (email_cfg.get("smtp_server") and
               email_cfg.get("username") and
               email_cfg.get("password") and
               email_cfg.get("username") != "your-assistant-email@gmail.com")
    if smtp_ok:
        print("Email:            [OK] SMTP credentials present")
    else:
        print("Email:            [FAIL] SMTP credentials missing or placeholder")

    # 3. Alpaca
    try:
        import requests
        alpaca_cfg = config.get("alpaca", {})
        api_key = alpaca_cfg.get("api_key", "")
        api_secret = alpaca_cfg.get("api_secret", "")
        base_url = alpaca_cfg.get("base_url", "https://paper-api.alpaca.markets")
        if api_key and api_key != "YOUR_PAPER_API_KEY":
            resp = requests.get(
                f"{base_url}/v2/account",
                headers={
                    "APCA-API-KEY-ID": api_key,
                    "APCA-API-SECRET-KEY": api_secret,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                acct = resp.json()
                equity = acct.get("equity", "?")
                print(f"Alpaca:           [OK] Paper account connected (equity: ${float(equity):,.0f})")
            else:
                print(f"Alpaca:           [FAIL] API returned {resp.status_code}")
        else:
            print("Alpaca:           [FAIL] API key is placeholder")
    except Exception as e:
        print(f"Alpaca:           [FAIL] {e}")

    # 4. Shadow trading
    shadow_cfg = config.get("shadow_trading", {})
    if shadow_cfg.get("enabled", False):
        print("Shadow Trading:   [OK] Enabled")
    else:
        print("Shadow Trading:   [WARN] Disabled")

    # 5. Ollama
    ollama_available = is_llm_available()
    llm_cfg = config.get("llm", {})
    model = llm_cfg.get("model", "qwen3:8b")
    if ollama_available:
        print(f"Ollama:           [OK] Running (model: {model})")
    else:
        print("Ollama:           [FAIL] Not reachable at localhost:11434")

    # 6. LLM test
    if ollama_available and llm_cfg.get("enabled", False):
        test_result = generate("Say hello in one sentence.", "You are a helpful assistant.")
        if test_result:
            print("LLM:              [OK] Enabled, test generation OK")
        else:
            print("LLM:              [WARN] Enabled but test generation failed")
    elif not llm_cfg.get("enabled", False):
        print("LLM:              [WARN] Disabled (will use template fallback)")
    else:
        print("LLM:              [WARN] Disabled (Ollama not available, will use template fallback)")

    # 7. Journal DB
    try:
        import sqlite3
        from pathlib import Path
        db_path = Path("ai_research_desk.sqlite3")
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT COUNT(*) FROM recommendations")
            count = cursor.fetchone()[0]
            conn.close()
            print(f"Journal DB:       [OK] Initialized ({count} recommendations)")
        else:
            print("Journal DB:       [WARN] Not initialized (run init-db)")
    except Exception as e:
        print(f"Journal DB:       [FAIL] {e}")

    # 8. Bootcamp
    bootcamp_cfg = config.get("bootcamp", {})
    if bootcamp_cfg.get("enabled", False):
        phase = bootcamp_cfg.get("phase", 1)
        print(f"Bootcamp:         [OK] Enabled (Phase {phase})")
    else:
        print("Bootcamp:         [WARN] Disabled")

    print("")
    print("All checks complete. Run 'python -m src.main watch' to start.")
    print("")


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
    scan.add_argument("--no-shadow", action="store_true", help="Skip shadow trading")
    scan.set_defaults(func=cmd_scan)

    mw = subparsers.add_parser("morning-watchlist", help="Generate and send morning watchlist")
    mw.add_argument("--email", action="store_true", help="Send watchlist and action packets via email")
    mw.add_argument("--dry-run", action="store_true", help="Print only, no email or journal writes")
    mw.set_defaults(func=cmd_morning_watchlist)

    eod = subparsers.add_parser("eod-recap", help="Generate and send EOD recap")
    eod.add_argument("--email", action="store_true", help="Send EOD recap via email")
    eod.add_argument("--dry-run", action="store_true", help="Print only, no email")
    eod.set_defaults(func=cmd_eod_recap)

    # Shadow ledger commands
    shadow_status = subparsers.add_parser("shadow-status", help="Show open shadow trades")
    shadow_status.set_defaults(func=cmd_shadow_status)

    shadow_history = subparsers.add_parser("shadow-history", help="Show closed shadow trades")
    shadow_history.add_argument("--days", type=int, default=30, help="Lookback period in days")
    shadow_history.set_defaults(func=cmd_shadow_history)

    shadow_close = subparsers.add_parser("shadow-close", help="Manually close a shadow trade")
    shadow_close.add_argument("ticker", help="Ticker to close")
    shadow_close.add_argument("--reason", default="manual", help="Exit reason")
    shadow_close.set_defaults(func=cmd_shadow_close)

    shadow_account = subparsers.add_parser("shadow-account", help="Alpaca paper account summary")
    shadow_account.set_defaults(func=cmd_shadow_account)

    # Review commands
    review = subparsers.add_parser("review", help="Review trades (use 'review list' or 'review <ID>')")
    review.add_argument("review_sub", nargs="?", default="list", help="'list' or a recommendation ID")
    review.set_defaults(func=cmd_review)

    mark_exec = subparsers.add_parser("mark-executed", help="Mark a trade as executed by Ryan")
    mark_exec.add_argument("ticker", help="Ticker to mark as executed")
    mark_exec.set_defaults(func=cmd_mark_executed)

    # Scorecard commands
    scorecard = subparsers.add_parser("review-scorecard", help="Generate weekly scorecard")
    scorecard.add_argument("--weeks", type=int, default=1, help="Number of weeks to cover")
    scorecard.add_argument("--email", action="store_true", help="Send scorecard via email")
    scorecard.set_defaults(func=cmd_review_scorecard)

    bootcamp = subparsers.add_parser("review-bootcamp", help="Generate bootcamp report")
    bootcamp.add_argument("--days", type=int, default=30, help="Bootcamp period in days")
    bootcamp.add_argument("--email", action="store_true", help="Send report via email")
    bootcamp.set_defaults(func=cmd_review_bootcamp)

    # Postmortem commands
    postmortems = subparsers.add_parser("postmortems", help="List recent postmortems")
    postmortems.add_argument("--limit", type=int, default=10, help="Max postmortems to show")
    postmortems.add_argument("--ticker", help="Filter by ticker")
    postmortems.set_defaults(func=cmd_postmortems)

    postmortem = subparsers.add_parser("postmortem", help="View full postmortem for a trade")
    postmortem.add_argument("recommendation_id", help="Recommendation ID to view")
    postmortem.set_defaults(func=cmd_postmortem_detail)

    # Watch loop and preflight
    watch = subparsers.add_parser("watch", help="Run automated daily cadence loop")
    watch.add_argument("--email-mode", choices=["full_stream", "daily_summary", "silent"],
                       default=None, help="Email delivery mode (default from config)")
    watch.set_defaults(func=cmd_watch)

    preflight = subparsers.add_parser("preflight", help="Run system preflight checks")
    preflight.set_defaults(func=cmd_preflight)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
