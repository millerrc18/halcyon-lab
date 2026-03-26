"""Halcyon Lab CLI — thin command dispatcher using service layer."""

import argparse
import json

from src.email.notifier import send_email
from src.journal.store import initialize_database
from src.packets.template import build_demo_packet


# ── Core Pipeline ─────────────────────────────────────────────────────

def cmd_init_db(args):
    initialize_database(args.db_path)
    print(f"Initialized journal database at {args.db_path}")


def cmd_demo_packet(args):
    print(build_demo_packet())


def cmd_send_test_email(args):
    success = send_email("[TRADE DESK] Test Email",
                         "This is a test from the AI Research Desk. Email delivery is working.")
    print("Test email sent successfully." if success else "Failed to send test email.")


def cmd_send_test_telegram(args):
    from src.notifications.telegram import send_telegram, is_telegram_enabled
    if not is_telegram_enabled():
        print("Telegram not configured. Add telegram section to config/settings.local.yaml:")
        print("  telegram:")
        print("    enabled: true")
        print('    bot_token: "your-bot-token"')
        print('    chat_id: "your-chat-id"')
        return
    success = send_telegram(
        "🧪 <b>HALCYON LAB — TEST</b>\n"
        "Telegram notifications are working!\n"
        "You'll receive alerts for:\n"
        "  • Trade opens/closes\n"
        "  • Earnings warnings\n"
        "  • Overnight data collection\n"
        "  • System events"
    )
    print("Telegram test sent successfully! ✓" if success else "Failed to send Telegram message.")


def cmd_ingest(args):
    from src.data_ingestion.market_data import fetch_ohlcv, fetch_spy_benchmark
    from src.universe.sp100 import get_sp100_universe
    universe = get_sp100_universe()
    print(f"Fetching OHLCV data for {len(universe)} tickers + SPY...")
    ohlcv = fetch_ohlcv(universe)
    spy = fetch_spy_benchmark()
    print(f"Ingestion complete: {len(ohlcv)} succeeded, {len(universe)-len(ohlcv)} failed")
    if ohlcv:
        sample = next(iter(ohlcv.values()))
        print(f"  Date range: {sample.index.min().date()} to {sample.index.max().date()}")
    print(f"  SPY benchmark: {'OK' if not spy.empty else 'FAILED'}")


def cmd_scan(args):
    from src.config import load_config
    from src.services.scan_service import run_scan
    config = load_config()
    result = run_scan(config, dry_run=getattr(args, "dry_run", False),
                      send_email_flag=getattr(args, "email", False),
                      run_shadow=not getattr(args, "no_shadow", False))
    verbose = getattr(args, "verbose", False)
    if verbose:
        print(f"Universe: {result['tickers_scanned']} ({result['tickers_succeeded']} OK)")
        for r in (result.get("ranked") or [])[:15]:
            feat = r["features"]
            tag = f"  [EARNINGS]" if feat.get("event_risk_level") in ("elevated", "imminent") else ""
            print(f"  {r['ticker']:6s}  score={r['score']:5.1f}  {r['qualification']}{tag}")
    if not result["packet_worthy"]:
        print(f"No packet-worthy setups. {len(result['watchlist'])} on watchlist.")
    else:
        print(f"\nPACKET-WORTHY: {len(result['packet_worthy'])}")
        for p in result["packet_worthy"]:
            print(p["rendered_text"])
    if result["watchlist"]:
        print(f"\nWATCHLIST ({len(result['watchlist'])}):")
        for w in result["watchlist"]:
            print(f"  {w['ticker']:6s}  score={w['score']:5.1f}  trend={w.get('trend_state','n/a')}")
    if getattr(args, "dry_run", False):
        print("\n[DRY RUN] No journal entries written.")


def cmd_morning_watchlist(args):
    from src.config import load_config
    from src.services.watchlist_service import generate_morning_watchlist
    result = generate_morning_watchlist(load_config(), send_email_flag=getattr(args, "email", False) and not getattr(args, "dry_run", False))
    print(result["email_body"])


def cmd_eod_recap(args):
    from src.config import load_config
    from src.services.recap_service import generate_eod_recap
    result = generate_eod_recap(load_config(), send_email_flag=getattr(args, "email", False) and not getattr(args, "dry_run", False))
    print(result["email_body"])


# ── Shadow Ledger ─────────────────────────────────────────────────────

def cmd_shadow_status(args):
    from src.config import load_config
    from src.services.shadow_service import get_shadow_status
    result = get_shadow_status(load_config())
    if not result["open_trades"]:
        print("SHADOW LEDGER — No open trades.")
        return
    print(f"\nSHADOW LEDGER — OPEN TRADES ({result['open_count']}):")
    for t in result["open_trades"]:
        pnl = f"${t['pnl_dollars']:+.2f} {t['pnl_pct']:+.1f}%" if t["pnl_dollars"] is not None else "n/a"
        cur = f"${t['current_price']:.2f}" if t["current_price"] else "n/a"
        print(f"  {t['ticker']:6s}  entry=${t['entry_price']:.2f}  current={cur}  P&L={pnl}  day {t['duration_days'] or 0}/{t['timeout_days']}")


def cmd_shadow_history(args):
    from src.services.shadow_service import get_shadow_history
    result = get_shadow_history(days=getattr(args, "days", 30))
    if not result["trades"]:
        print(f"SHADOW LEDGER — No closed trades in the last {args.days} days.")
        return
    print(f"\nSHADOW LEDGER — CLOSED TRADES:")
    for t in result["trades"]:
        print(f"  {t['ticker']:6s}  P&L=${t.get('pnl_dollars',0):+.2f}  {t.get('exit_reason','?')}")
    m = result["metrics"]
    print(f"\n  {m['total_trades']} trades | {m['win_rate']:.0f}% WR | expectancy ${m['expectancy']:+.2f}")


def cmd_shadow_close(args):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from src.journal.store import get_open_shadow_trades, close_shadow_trade
    from src.shadow_trading.executor import _get_current_price_safe
    ticker = args.ticker.upper()
    reason = getattr(args, "reason", "manual")
    trade = next((t for t in get_open_shadow_trades() if t["ticker"] == ticker), None)
    if not trade:
        print(f"No open shadow trade found for {ticker}.")
        return
    entry = trade.get("actual_entry_price") or trade.get("entry_price", 0)
    current = _get_current_price_safe(ticker) or entry
    shares = trade.get("planned_shares", 1)
    pnl_dollars = round((current - entry) * shares, 2)
    pnl_pct = round((current - entry) / entry * 100, 2) if entry > 0 else 0
    et = ZoneInfo("America/New_York")
    now = datetime.now(et)
    try:
        from src.shadow_trading.alpaca_adapter import place_paper_exit
        place_paper_exit(ticker, shares)
    except Exception:
        pass
    close_shadow_trade(trade["trade_id"], exit_price=current, exit_time=now.isoformat(),
                       exit_reason=reason, pnl_dollars=pnl_dollars, pnl_pct=pnl_pct)
    print(f"Closed {ticker}: {reason} | P&L=${pnl_dollars:+.2f} ({pnl_pct:+.1f}%)")


def cmd_shadow_account(args):
    from src.services.shadow_service import get_shadow_account
    try:
        result = get_shadow_account()
        acct = result["account"]
        print(f"\nALPACA PAPER ACCOUNT: equity=${acct['equity']:.2f} cash=${acct['cash']:.2f}")
        for p in result.get("positions", []):
            print(f"  {p['symbol']:6s}  qty={p['qty']}  P&L=${p['unrealized_pl']:+.2f}")
    except Exception as e:
        print(f"Failed to connect to Alpaca: {e}")


# ── Live Trading ─────────────────────────────────────────────────────

def cmd_live_status(args):
    """Show live account balance and open positions."""
    from src.config import load_config
    config = load_config()
    live_cfg = config.get("live_trading", {})

    if not live_cfg.get("enabled", False):
        print("LIVE TRADING — Disabled in config.")
        print("  Set live_trading.enabled: true in settings.local.yaml")
        return

    try:
        from src.shadow_trading.alpaca_adapter import get_live_account_info, get_live_positions
        acct = get_live_account_info()
        print(f"\nLIVE ACCOUNT:")
        print(f"  Equity:       ${acct['equity']:.2f}")
        print(f"  Cash:         ${acct['cash']:.2f}")
        print(f"  Buying Power: ${acct['buying_power']:.2f}")
        print(f"  Status:       {acct['status']}")

        starting = live_cfg.get("starting_capital", 100)
        pnl = acct['equity'] - starting
        pnl_pct = (pnl / starting * 100) if starting > 0 else 0
        print(f"  Starting:     ${starting:.2f}")
        print(f"  Total P&L:    ${pnl:+.2f} ({pnl_pct:+.1f}%)")

        positions = get_live_positions()
        if positions:
            print(f"\n  OPEN POSITIONS ({len(positions)}):")
            for p in positions:
                print(f"    {p['symbol']:6s}  qty={p['qty']}  "
                      f"entry=${p['avg_entry_price']:.2f}  "
                      f"current=${p['current_price']:.2f}  "
                      f"P&L=${p['unrealized_pl']:+.2f}")
        else:
            print("\n  No open positions.")

    except Exception as e:
        print(f"Failed to connect to live Alpaca account: {e}")


def cmd_live_history(args):
    """Show live trade history from the journal."""
    import sqlite3
    days = getattr(args, "days", 30)
    try:
        from src.journal.store import initialize_database
        initialize_database()
        with sqlite3.connect("ai_research_desk.sqlite3") as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT ticker, actual_entry_price, actual_exit_price,
                       pnl_dollars, pnl_pct, exit_reason, created_at, actual_exit_time,
                       status
                FROM shadow_trades
                WHERE source = 'live'
                ORDER BY created_at DESC
                LIMIT 50"""
            ).fetchall()

        if not rows:
            print("LIVE TRADING — No live trades recorded.")
            return

        open_trades = [r for r in rows if r["status"] == "open"]
        closed_trades = [r for r in rows if r["status"] == "closed"]

        print(f"\nLIVE TRADE HISTORY:")

        if open_trades:
            print(f"\n  OPEN ({len(open_trades)}):")
            for t in open_trades:
                print(f"    {t['ticker']:6s}  entry=${(t['actual_entry_price'] or 0):.2f}  "
                      f"opened={t['created_at'][:10]}")

        if closed_trades:
            print(f"\n  CLOSED ({len(closed_trades)}):")
            total_pnl = 0.0
            wins = 0
            for t in closed_trades:
                pnl = t["pnl_dollars"] or 0
                total_pnl += pnl
                if pnl > 0:
                    wins += 1
                print(f"    {t['ticker']:6s}  P&L=${pnl:+.2f} ({(t['pnl_pct'] or 0):+.1f}%)  "
                      f"{t['exit_reason'] or '?'}  {(t['actual_exit_time'] or '')[:10]}")

            win_rate = (wins / len(closed_trades) * 100) if closed_trades else 0
            print(f"\n  Total: ${total_pnl:+.2f} | {len(closed_trades)} trades | "
                  f"{win_rate:.0f}% win rate")
    except Exception as e:
        print(f"Error loading live trade history: {e}")


def cmd_live_close(args):
    """Manually close a live position."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from src.journal.store import get_open_shadow_trades, close_shadow_trade
    from src.shadow_trading.executor import _get_current_price_safe

    ticker = args.ticker.upper()
    reason = getattr(args, "reason", "manual")

    # Find the live trade
    open_trades = get_open_shadow_trades()
    trade = next(
        (t for t in open_trades if t["ticker"] == ticker and t.get("source") == "live"),
        None,
    )
    if not trade:
        print(f"No open LIVE trade found for {ticker}.")
        return

    entry = trade.get("actual_entry_price") or trade.get("entry_price", 0)
    current = _get_current_price_safe(ticker) or entry
    shares = trade.get("planned_shares", 1)
    pnl_dollars = round((current - entry) * shares, 2)
    pnl_pct = round((current - entry) / entry * 100, 2) if entry > 0 else 0

    et = ZoneInfo("America/New_York")
    now = datetime.now(et)

    # Place live sell order
    try:
        from src.shadow_trading.alpaca_adapter import place_live_exit
        place_live_exit(ticker, shares)
    except Exception as e:
        print(f"WARNING: Live sell order failed: {e}")
        print("Closing journal record anyway.")

    close_shadow_trade(
        trade["trade_id"], exit_price=current, exit_time=now.isoformat(),
        exit_reason=reason, pnl_dollars=pnl_dollars, pnl_pct=pnl_pct,
    )
    print(f"Closed LIVE {ticker}: {reason} | P&L=${pnl_dollars:+.2f} ({pnl_pct:+.1f}%)")


# ── Review & Evaluation ──────────────────────────────────────────────

def cmd_review(args):
    from src.services.review_service import get_pending_reviews, get_recommendation, submit_review
    sub = getattr(args, "review_sub", "list")
    if sub == "list" or not sub:
        pending = get_pending_reviews()
        if not pending:
            print("No trades pending review.")
            return
        print(f"\nTRADES PENDING REVIEW ({len(pending)}):")
        for r in pending:
            pnl = f"${r.get('shadow_pnl_dollars', 0):+.2f}" if r.get("shadow_pnl_dollars") is not None else "n/a"
            print(f"  {r['recommendation_id'][:8]}..  {r.get('ticker','?'):6s}  {r.get('created_at','')[:10]}  P&L={pnl}")
        return
    rec = get_recommendation(sub)
    if not rec:
        print(f"Recommendation {sub} not found.")
        return
    print(f"\nREVIEW: {rec['ticker']} — score {rec.get('confidence_score','n/a')}/10")
    try:
        approved = input("  Approved? (y/n): ").strip().lower()
        grade = input("  Grade (A/B/C/D/F): ").strip().upper()
        notes = input("  Notes: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return
    submit_review(sub, {"ryan_approved": 1 if approved == "y" else 0,
                        "user_grade": grade if grade in "ABCDF" else None,
                        "ryan_notes": notes or None})
    print(f"Review saved for {rec['ticker']}.")


def cmd_mark_executed(args):
    from src.services.review_service import mark_executed
    if mark_executed(args.ticker):
        print(f"Marked {args.ticker.upper()} as executed.")
    else:
        print(f"No recommendation found for {args.ticker.upper()}.")


def cmd_review_scorecard(args):
    from src.services.review_service import get_scorecard
    print(get_scorecard(weeks=getattr(args, "weeks", 1)))

def cmd_review_bootcamp(args):
    from src.services.review_service import get_bootcamp_report
    print(get_bootcamp_report(days=getattr(args, "days", 30)))

def cmd_postmortems(args):
    from src.services.review_service import get_postmortems
    results = get_postmortems(limit=getattr(args, "limit", 10), ticker=getattr(args, "ticker", None))
    if not results:
        print("No postmortems available.")
        return
    for r in results:
        print(f"  {r['ticker']:6s}  {r['date']}  {r['exit_reason']:>12s}  ${r['pnl_dollars']:+.2f}  {r['postmortem'][:60]}")

def cmd_postmortem_detail(args):
    from src.services.review_service import get_postmortem_detail
    rec = get_postmortem_detail(args.recommendation_id)
    if not rec:
        print(f"Not found: {args.recommendation_id}")
        return
    print(f"\nPOSTMORTEM: {rec['ticker']}")
    if rec.get("assistant_postmortem"):
        print(rec["assistant_postmortem"])


# ── Training ──────────────────────────────────────────────────────────

def cmd_training_status(args):
    from src.services.training_service import get_training_status
    s = get_training_status()
    print(f"\nTRAINING STATUS")
    print(f"  Model: {s['model_name']} | Dataset: {s['dataset_total']} examples | New: {s['new_since_last_train']}")
    print(f"  Train queued: {s['train_queued']} ({s['train_reason']})")
    print(f"  Rollback: {s['rollback_status']}")

def cmd_training_history(args):
    from src.services.training_service import get_training_history
    h = get_training_history()
    print(f"\nMODEL VERSION HISTORY")
    for v in h["versions"]:
        wr = f"{v['win_rate']:.1f}%" if v.get("win_rate") else "n/a"
        print(f"  {v['version_name']:<14s} {v['status']:<10s} trades={v['trade_count']}  WR={wr}")

def cmd_training_report(args):
    from src.services.training_service import get_training_report
    print(get_training_report())

def cmd_bootstrap_training(args):
    from src.training.bootstrap import estimate_bootstrap_cost, generate_synthetic_training_data
    count = getattr(args, "count", 500)
    cost = estimate_bootstrap_cost(count)
    print(f"Bootstrap: {count} examples, est. ${cost:.2f}")
    if not getattr(args, "yes", False):
        if input("Proceed? [y/N] ").strip().lower() != "y":
            print("Aborted.")
            return
    created = generate_synthetic_training_data(count)
    print(f"Bootstrap complete: {created} examples created")

def cmd_backfill_training(args):
    from src.training.backfill import estimate_backfill_cost, run_historical_backfill
    months = getattr(args, "months", 12)
    max_ex = getattr(args, "max_examples", 2000)
    quality_filter = ["clean_win", "clean_loss"]
    if getattr(args, "include_messy", False):
        quality_filter = ["clean_win", "clean_loss", "messy", "timeout"]
    cost = estimate_backfill_cost(max_ex)
    print(f"Backfill: {months}mo, max {max_ex} examples, est. ${cost:.2f}")
    if not getattr(args, "yes", False):
        if input("Proceed? [y/N] ").strip().lower() != "y":
            print("Aborted.")
            return
    stats = run_historical_backfill(months=months, min_score=getattr(args, "min_score", 70),
                                    quality_filter=quality_filter, max_examples=max_ex)
    print(f"Backfill complete: {stats['examples_generated']} examples, ${stats['estimated_cost']:.2f}")

def cmd_train(args):
    from src.training.trainer import run_fine_tune, export_training_data, should_train
    from src.training.versioning import rollback_model
    if getattr(args, "rollback", False):
        restored = rollback_model()
        print(f"Rolled back to {restored['version_name']}" if restored else "Rollback failed.")
        return
    if getattr(args, "export", False):
        split, count = export_training_data()
        print(f"Exported {count} examples ({split.get('training',0)} train, {split.get('holdout',0)} holdout)")
        return
    if not getattr(args, "force", False):
        trigger, reason = should_train()
        if not trigger:
            print(f"Training not needed: {reason}\nUse --force to train anyway.")
            return
    result = run_fine_tune()
    print(f"Training complete: {result['version_name']}" if result else "Training failed.")


# ── Training Quality Commands ─────────────────────────────────────────

def cmd_classify_training(args):
    from src.training.curriculum import classify_all_examples
    result = classify_all_examples()
    print(f"Classified {result['classified']} examples")
    print(f"  Difficulty: {result['difficulty']}")
    print(f"  Stages: {result['stage']}")

def cmd_score_training(args):
    from src.training.quality_filter import score_all_unscored
    result = score_all_unscored()
    print(f"Scored {result['scored']} examples (avg: {result['avg_score']:.2f}), skipped {result['skipped']}")

def cmd_validate_training(args):
    from src.training.validation import validate_training_dataset
    result = validate_training_dataset()
    print(f"\nDATASET VALIDATION ({result['total_examples']} examples)")
    print(f"  Health: {result['overall_health']}")
    print(f"  Format compliance: {result['format_compliance']:.0%}")
    print(f"  Win/loss: {result['wins']}W/{result['losses']}L ({result['win_pct']:.0%})")
    print(f"  Tickers: {result['tickers_represented']} | Sectors: {result['sectors_covered']}")
    print(f"  Duplicates: {result['exact_duplicates']} exact, {result['near_duplicates']} near")
    if result["issues"]:
        print(f"  Issues: {'; '.join(result['issues'])}")

def cmd_generate_contrastive(args):
    from src.training.curriculum import generate_contrastive_training_data
    count = generate_contrastive_training_data(max_pairs=getattr(args, "max_pairs", 50))
    print(f"Generated {count} contrastive training examples")

def cmd_generate_preferences(args):
    from src.training.dpo_pipeline import generate_preference_pairs
    count = generate_preference_pairs(n_pairs=getattr(args, "count", 100))
    print(f"Generated {count} preference pairs")


# ── Evaluation Commands ───────────────────────────────────────────────

def cmd_cto_report(args):
    from src.evaluation.cto_report import generate_cto_report, format_cto_report
    report = generate_cto_report(days=getattr(args, "days", 7))
    if getattr(args, "json", False):
        print(json.dumps(report, indent=2, default=str))
    else:
        print(format_cto_report(report))
    if getattr(args, "email", False):
        body = json.dumps(report, indent=2, default=str) if getattr(args, "json", False) else format_cto_report(report)
        send_email(f"[TRADE DESK] CTO Report", body)

def cmd_evaluate_holdout(args):
    from src.training.trainer import evaluate_on_holdout
    print(json.dumps(evaluate_on_holdout(model_name=getattr(args, "model", "halcyon-latest")), indent=2))

def cmd_model_evaluation_status(args):
    from src.training.ab_evaluation import get_evaluation_status
    status = get_evaluation_status()
    if not status:
        print("No model in A/B evaluation.")
        return
    print(f"A/B: {status['model_name']} | {status['evaluations']} evals | WR={status['win_rate']:.0%} | {status['recommendation']}")

def cmd_promote_model(args):
    from src.training.ab_evaluation import check_promotion_ready
    from src.training.versioning import get_evaluation_model, promote_evaluation_model
    eval_model = get_evaluation_model()
    if not eval_model:
        print("No model in evaluation.")
        return
    if not getattr(args, "force", False):
        status = check_promotion_ready(eval_model["version_name"])
        if not status["ready"]:
            print(f"Not ready: {status['recommendation']}. Use --force.")
            return
    promoted = promote_evaluation_model()
    print(f"Promoted {promoted['version_name']}" if promoted else "Promotion failed.")

def cmd_feature_importance(args):
    from src.evaluation.feature_importance import compute_feature_importance
    result = compute_feature_importance(days=getattr(args, "days", 30))
    print(f"\nFEATURE IMPORTANCE ({result['closed_trades']} trades)")
    for f in result.get("features", []):
        print(f"  {f['name']:25s}  corr={f['correlation_with_pnl']:+.3f}  [{f['predictive_power']}]")

def cmd_backtest(args):
    from src.evaluation.backtester import backtest_model
    print(json.dumps(backtest_model(getattr(args, "model", "halcyon-latest"),
                                     months=getattr(args, "months", 6)), indent=2, default=str))

def cmd_compare_models(args):
    from src.evaluation.backtester import compare_models
    print(json.dumps(compare_models(args.model_a, args.model_b,
                                     months=getattr(args, "months", 3)), indent=2, default=str))

def cmd_check_leakage(args):
    from src.training.leakage_detector import check_outcome_leakage
    result = check_outcome_leakage()
    print("\n=== OUTCOME LEAKAGE TEST ===")
    if result.get("balanced_accuracy") is None:
        print(f"  {result.get('note', 'Insufficient data')}")
    else:
        print(f"  Status:            {result['status']}")
        print(f"  Balanced Accuracy: {result['balanced_accuracy']:.1%} (CLEAN ≤55%, MARGINAL 55-65%, LEAKING >65%)")
        print(f"  Raw Accuracy:      {result['raw_accuracy']:.1%}")
        print(f"  Majority Baseline: {result['majority_baseline']:.1%} (predicting all-majority-class)")
        print(f"  Above Baseline:    {result['accuracy_above_baseline']:+.1%}")
        cb = result.get("class_balance", {})
        print(f"  Class Balance:     {cb.get('wins', 0)} wins / {cb.get('losses', 0)} losses ({cb.get('win_pct', 0)}% win)")
        print(f"  Examples:          {result['n_examples']}")
        if result.get("feature_importance"):
            fi = result["feature_importance"]
            print(f"  Win predictors:    {', '.join(fi['win_predictors'][:3])}")
            print(f"  Loss predictors:   {', '.join(fi['loss_predictors'][:3])}")
        if result["is_leaking"]:
            print("\n  ACTION: Commentary text predicts outcomes beyond feature-level signal.")
            print("  Investigate whether language reveals directional expectations.")
        elif result["status"] == "MARGINAL":
            print("\n  MARGINAL: Some signal detected, likely feature-level (not outcome leakage).")
            print("  Safe to proceed with training. Monitor on future datasets.")
        else:
            print("\n  Commentary is outcome-independent. Safe to fine-tune.")


# ── Operations ────────────────────────────────────────────────────────

def cmd_halt_trading(args):
    from src.risk.governor import _global_halt
    _global_halt(True)
    print("[RISK] All trading halted. Use 'resume-trading' to resume.")

def cmd_resume_trading(args):
    from src.risk.governor import _global_halt
    _global_halt(False)
    print("[RISK] Trading resumed.")

def cmd_preflight(args):
    from src.config import load_config
    from src.services.system_service import get_system_status
    s = get_system_status(load_config())
    print("\nHALCYON LAB - PREFLIGHT CHECK")
    print(f"  Config:    {'OK' if s['config_loaded'] else 'FAIL'}")
    print(f"  Email:     {'OK' if s['email_configured'] else 'FAIL'}")
    print(f"  Alpaca:    {'OK' if s['alpaca_connected'] else 'FAIL'} {'$'+str(int(s['alpaca_equity'])) if s['alpaca_equity'] else ''}")
    print(f"  Shadow:    {'Enabled' if s['shadow_trading_enabled'] else 'Disabled'}")
    print(f"  Ollama:    {'OK' if s['ollama_available'] else 'FAIL'}")
    print(f"  LLM:       {'OK ('+s['llm_model']+')' if s['llm_enabled'] and s['ollama_available'] else 'Disabled'}")
    print(f"  Model:     {s['model_version']}")
    print(f"  Journal:   {s['journal_recommendations']} recs, {s['journal_shadow_trades']} trades")
    print(f"  Training:  {'Enabled ('+str(s['training_examples'])+' examples)' if s['training_enabled'] else 'Disabled'}")
    print(f"  Bootcamp:  {'Phase '+str(s['bootcamp_phase']) if s['bootcamp_enabled'] else 'Disabled'}")

def cmd_train_pipeline(args):
    """Run the complete training pipeline end-to-end."""
    from src.training.quality_filter import score_all_unscored
    from src.training.leakage_detector import check_outcome_leakage
    from src.training.curriculum import classify_all_examples
    from src.training.trainer import run_fine_tune

    print("\n=== HALCYON TRAINING PIPELINE ===\n")

    # Step 1: Score unscored examples
    print("[1/5] Scoring unscored training examples...")
    result = score_all_unscored()
    scored = result.get("scored", 0)
    print(f"  Scored {scored} examples")

    # Step 2: Check for outcome leakage
    print("\n[2/5] Running outcome leakage test...")
    leakage = check_outcome_leakage()
    if leakage.get("is_leaking"):
        print(f"  LEAKING — balanced accuracy {leakage['balanced_accuracy']:.1%}")
        if not args.force:
            print("  ABORT: Fix leakage before training. Use --force to override.")
            return
        print("  --force: Proceeding despite leakage warning")
    else:
        ba = leakage.get("balanced_accuracy")
        status = leakage.get("status", "CLEAN")
        print(f"  {status} — balanced accuracy {ba:.1%}" if ba else f"  {status}")

    # Step 3: Classify examples into curriculum stages
    print("\n[3/5] Classifying training examples...")
    classify_result = classify_all_examples()
    print(f"  Classified {classify_result.get('classified', 0)} examples")

    # Step 4: Export training data (handled inside run_fine_tune)
    print("\n[4/5] Exporting training data...")

    # Step 5: Fine-tune
    print("\n[5/5] Starting fine-tuning...")
    ft_result = run_fine_tune()
    if ft_result:
        print(f"\n  Model registered: {ft_result.get('version_name', 'halcyon-latest')}")
        print("  TRAINING PIPELINE COMPLETE")
    else:
        print("\n  Training failed. Check logs.")


def cmd_collect_data(args):
    """Run data collection pipeline manually."""
    from src.data_collection.options_collector import collect_options_chains
    from src.data_collection.options_metrics import compute_options_metrics
    from src.data_collection.vix_collector import collect_vix_term_structure
    from src.data_collection.macro_collector import collect_macro_snapshots
    from src.data_collection.cboe_collector import collect_cboe_ratios
    from src.data_collection.trends_collector import collect_google_trends
    from src.universe.sp100 import get_sp100_universe

    print("\n=== DATA COLLECTION ===\n")
    universe = get_sp100_universe()

    print("[1/7] Collecting options chains...")
    r = collect_options_chains(universe)
    print(f"  {r}")

    print("[2/7] Computing options metrics...")
    r = compute_options_metrics(universe)
    print(f"  {r}")

    print("[3/7] VIX term structure...")
    r = collect_vix_term_structure()
    print(f"  {r}")

    print("[4/7] CBOE ratios...")
    r = collect_cboe_ratios()
    print(f"  {r}")

    print("[5/7] FRED macro indicators...")
    r = collect_macro_snapshots()
    print(f"  {r}")

    print("[6/7] Google Trends (batch)...")
    r = collect_google_trends(universe, batch_size=20)
    print(f"  {r}")

    print("[7/7] Earnings calendar...")
    try:
        from scripts.fetch_earnings_calendar import fetch_earnings_dates
        r = fetch_earnings_dates(universe)
        print(f"  {r}")
        upcoming = r.get("upcoming_7d", [])
        if upcoming:
            print(f"\n  ⚠️  EARNINGS THIS WEEK:")
            for item in upcoming:
                print(f"    • {item}")
    except Exception as e:
        print(f"  Earnings fetch failed: {e}")

    print("\nData collection complete.")


def cmd_fetch_earnings(args):
    """Fetch upcoming earnings dates for S&P 100."""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from scripts.fetch_earnings_calendar import fetch_earnings_dates, get_all_upcoming_earnings
    from src.universe.sp100 import get_sp100_universe

    universe = get_sp100_universe()
    print(f"\n{'='*60}")
    print(f"EARNINGS CALENDAR — S&P 100")
    print(f"{'='*60}")
    print(f"Fetching for {len(universe)} tickers...\n")

    result = fetch_earnings_dates(universe)
    print(f"\nResults: {result['tickers_with_dates']} tickers with dates, {result['errors']} errors")

    if result["upcoming_7d"]:
        print(f"\n⚠️  EARNINGS THIS WEEK ({len(result['upcoming_7d'])}):")
        for item in result["upcoming_7d"]:
            print(f"  • {item}")

    upcoming = get_all_upcoming_earnings(days=14)
    if upcoming:
        print(f"\n📅 NEXT 14 DAYS ({len(upcoming)} stocks):")
        for item in upcoming:
            print(f"  • {item['ticker']:6s} {item['earnings_date']} ({item['days_away']}d) {item.get('earnings_time') or ''}")


def cmd_council(args):
    from src.council.engine import CouncilEngine
    session_type = getattr(args, "type", "daily")
    print(f"Running AI Council session (type: {session_type})...")
    engine = CouncilEngine()
    result = engine.run_session(session_type=session_type)
    consensus = result.get("consensus", "unknown")
    contested = result.get("is_contested", False)
    print(f"\nConsensus: {consensus.upper()}"
          f"{' (CONTESTED)' if contested else ''}")
    print(f"Rounds: {result.get('rounds_completed', 0)} | "
          f"Cost: ${result.get('total_cost', 0):.2f}")

def cmd_watch(args):
    from src.config import load_config
    from src.scheduler.watch import WatchLoop
    WatchLoop(load_config(), email_mode=getattr(args, "email_mode", None),
              overnight=getattr(args, "overnight", False)).run()

def cmd_dashboard(args):
    import uvicorn
    port = getattr(args, "port", 8000)
    print(f"Starting dashboard at http://localhost:{port}")
    uvicorn.run("src.api.app:app", host="0.0.0.0", port=port, reload=False)


# ── Argument Parser ───────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Halcyon Lab — AI Trading Desk")
    sp = p.add_subparsers(dest="command", required=True)

    # Core pipeline
    _p = sp.add_parser("init-db"); _p.add_argument("--db-path", default="ai_research_desk.sqlite3"); _p.set_defaults(func=cmd_init_db)
    sp.add_parser("demo-packet").set_defaults(func=cmd_demo_packet)
    sp.add_parser("send-test-email").set_defaults(func=cmd_send_test_email)
    sp.add_parser("send-test-telegram", help="Test Telegram notification delivery").set_defaults(func=cmd_send_test_telegram)
    sp.add_parser("ingest").set_defaults(func=cmd_ingest)

    _p = sp.add_parser("scan"); _p.add_argument("--verbose", action="store_true"); _p.add_argument("--email", action="store_true"); _p.add_argument("--dry-run", action="store_true"); _p.add_argument("--no-shadow", action="store_true"); _p.set_defaults(func=cmd_scan)
    _p = sp.add_parser("morning-watchlist"); _p.add_argument("--email", action="store_true"); _p.add_argument("--dry-run", action="store_true"); _p.set_defaults(func=cmd_morning_watchlist)
    _p = sp.add_parser("eod-recap"); _p.add_argument("--email", action="store_true"); _p.add_argument("--dry-run", action="store_true"); _p.set_defaults(func=cmd_eod_recap)

    # Shadow ledger
    sp.add_parser("shadow-status").set_defaults(func=cmd_shadow_status)
    _p = sp.add_parser("shadow-history"); _p.add_argument("--days", type=int, default=30); _p.set_defaults(func=cmd_shadow_history)
    _p = sp.add_parser("shadow-close"); _p.add_argument("ticker"); _p.add_argument("--reason", default="manual"); _p.set_defaults(func=cmd_shadow_close)
    sp.add_parser("shadow-account").set_defaults(func=cmd_shadow_account)

    # Live trading
    sp.add_parser("live-status", help="Show live account balance and open positions").set_defaults(func=cmd_live_status)
    _p = sp.add_parser("live-history", help="Show live trade history"); _p.add_argument("--days", type=int, default=30); _p.set_defaults(func=cmd_live_history)
    _p = sp.add_parser("live-close", help="Close a live position"); _p.add_argument("ticker"); _p.add_argument("--reason", default="manual"); _p.set_defaults(func=cmd_live_close)

    # Review
    _p = sp.add_parser("review"); _p.add_argument("review_sub", nargs="?", default="list"); _p.set_defaults(func=cmd_review)
    _p = sp.add_parser("mark-executed"); _p.add_argument("ticker"); _p.set_defaults(func=cmd_mark_executed)
    _p = sp.add_parser("review-scorecard"); _p.add_argument("--weeks", type=int, default=1); _p.add_argument("--email", action="store_true"); _p.set_defaults(func=cmd_review_scorecard)
    _p = sp.add_parser("review-bootcamp"); _p.add_argument("--days", type=int, default=30); _p.add_argument("--email", action="store_true"); _p.set_defaults(func=cmd_review_bootcamp)
    _p = sp.add_parser("postmortems"); _p.add_argument("--limit", type=int, default=10); _p.add_argument("--ticker"); _p.set_defaults(func=cmd_postmortems)
    _p = sp.add_parser("postmortem"); _p.add_argument("recommendation_id"); _p.set_defaults(func=cmd_postmortem_detail)

    # Training — data
    sp.add_parser("training-status").set_defaults(func=cmd_training_status)
    sp.add_parser("training-history").set_defaults(func=cmd_training_history)
    _p = sp.add_parser("training-report"); _p.add_argument("--email", action="store_true"); _p.set_defaults(func=cmd_training_report)
    _p = sp.add_parser("bootstrap-training"); _p.add_argument("--count", type=int, default=500); _p.add_argument("--yes", action="store_true"); _p.set_defaults(func=cmd_bootstrap_training)
    _p = sp.add_parser("backfill-training"); _p.add_argument("--months", type=int, default=12); _p.add_argument("--max-examples", type=int, default=2000); _p.add_argument("--min-score", type=float, default=70); _p.add_argument("--include-messy", action="store_true"); _p.add_argument("--yes", action="store_true"); _p.set_defaults(func=cmd_backfill_training)
    _p = sp.add_parser("train"); _p.add_argument("--force", action="store_true"); _p.add_argument("--rollback", action="store_true"); _p.add_argument("--export", action="store_true"); _p.set_defaults(func=cmd_train)
    _p = sp.add_parser("train-pipeline", help="Run complete training pipeline (score → leakage → classify → train)"); _p.add_argument("--force", action="store_true", help="Continue even if leakage detected"); _p.set_defaults(func=cmd_train_pipeline)

    # Training — quality
    sp.add_parser("classify-training-data").set_defaults(func=cmd_classify_training)
    sp.add_parser("score-training-data").set_defaults(func=cmd_score_training)
    sp.add_parser("validate-training-data").set_defaults(func=cmd_validate_training)
    _p = sp.add_parser("generate-contrastive"); _p.add_argument("--max-pairs", type=int, default=50); _p.set_defaults(func=cmd_generate_contrastive)
    _p = sp.add_parser("generate-preferences"); _p.add_argument("--count", type=int, default=100); _p.set_defaults(func=cmd_generate_preferences)

    # Evaluation
    _p = sp.add_parser("cto-report"); _p.add_argument("--days", type=int, default=7); _p.add_argument("--json", action="store_true"); _p.add_argument("--email", action="store_true"); _p.set_defaults(func=cmd_cto_report)
    _p = sp.add_parser("evaluate-holdout"); _p.add_argument("--model", default="halcyon-latest"); _p.set_defaults(func=cmd_evaluate_holdout)
    sp.add_parser("model-evaluation-status").set_defaults(func=cmd_model_evaluation_status)
    _p = sp.add_parser("promote-model"); _p.add_argument("--force", action="store_true"); _p.set_defaults(func=cmd_promote_model)
    _p = sp.add_parser("feature-importance"); _p.add_argument("--days", type=int, default=30); _p.set_defaults(func=cmd_feature_importance)
    _p = sp.add_parser("backtest"); _p.add_argument("--model", default="halcyon-latest"); _p.add_argument("--months", type=int, default=6); _p.set_defaults(func=cmd_backtest)
    _p = sp.add_parser("compare-models"); _p.add_argument("--model-a", required=True); _p.add_argument("--model-b", required=True); _p.add_argument("--months", type=int, default=3); _p.set_defaults(func=cmd_compare_models)
    sp.add_parser("check-leakage").set_defaults(func=cmd_check_leakage)

    # Operations
    sp.add_parser("collect-data", help="Run market data collection pipeline").set_defaults(func=cmd_collect_data)
    sp.add_parser("fetch-earnings", help="Fetch upcoming earnings dates for S&P 100").set_defaults(func=cmd_fetch_earnings)
    sp.add_parser("halt-trading").set_defaults(func=cmd_halt_trading)
    sp.add_parser("resume-trading").set_defaults(func=cmd_resume_trading)
    sp.add_parser("preflight").set_defaults(func=cmd_preflight)
    _p = sp.add_parser("council", help="Run an AI Council session"); _p.add_argument("--type", default="daily", choices=["daily", "strategic", "on_demand"]); _p.set_defaults(func=cmd_council)
    _p = sp.add_parser("watch"); _p.add_argument("--email-mode", choices=["full_stream", "daily_summary", "silent"]); _p.add_argument("--overnight", action="store_true", help="Enable overnight schedule (post-close, news, enrichment, pre-market)"); _p.set_defaults(func=cmd_watch)
    _p = sp.add_parser("dashboard"); _p.add_argument("--port", type=int, default=8000); _p.set_defaults(func=cmd_dashboard)

    return p


def main():
    from src.log_config import setup_logging
    from src.config import load_config
    config = load_config()
    log_cfg = config.get("logging", {})
    setup_logging(
        level=log_cfg.get("level", "INFO"),
        log_file=log_cfg.get("file", "logs/halcyon.log"),
    )
    initialize_database()
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
