"""Watch loop for automated daily cadence.

Simple Python loop — no APScheduler or cron dependencies.
"""

import time
import logging
from datetime import datetime, date
from zoneinfo import ZoneInfo

from src.config import load_config
from src.llm.client import is_llm_available
from src.scheduler.scorer import GuardedScorer

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")


class WatchLoop:
    """Automated daily cadence loop for the AI Research Desk."""

    def __init__(self, config: dict, email_mode: str | None = None,
                 overnight: bool = False):
        self.config = config
        self.overnight = overnight
        auto_cfg = config.get("automation", {})
        bootcamp_cfg = config.get("bootcamp", {})
        bootcamp_enabled = bootcamp_cfg.get("enabled", False)

        self.morning_hour = auto_cfg.get("morning_watchlist_hour_et", 8)
        self.eod_hour = auto_cfg.get("eod_recap_hour_et", 16)
        self.market_open_hour = auto_cfg.get("market_open_hour_et", 9)
        self.market_open_minute = auto_cfg.get("market_open_minute_et", 30)
        self.market_close_hour = auto_cfg.get("market_close_hour_et", 16)

        # Bootcamp overrides
        if bootcamp_enabled:
            self.scan_interval = bootcamp_cfg.get("scan_interval_minutes", 30)
            default_email_mode = bootcamp_cfg.get("email_mode", "full_stream")
        else:
            self.scan_interval = auto_cfg.get("scan_interval_minutes", 30)
            default_email_mode = "full_stream"

        self.email_mode = email_mode or default_email_mode
        self.bootcamp_enabled = bootcamp_enabled
        self.bootcamp_phase = bootcamp_cfg.get("phase", 1) if bootcamp_enabled else None

        # Training config
        training_cfg = config.get("training", {})
        self.training_enabled = training_cfg.get("enabled", False)

        # Daily state (in-memory, resets on restart)
        self._morning_done = False
        self._eod_done = False
        self._last_scan_time: datetime | None = None
        self._daily_packets: list = []
        self._today: date | None = None
        self._trades_managed_today = 0
        self._training_collection_done = False
        self._training_run_done = False
        self._saturday_reports_done = False
        self._daily_audit_done = False
        self._consecutive_errors = 0

        # Overnight schedule flags
        self._post_close_done = False
        self._overnight_training_collection_done = False
        self._data_collection_done = False
        self._news_ingestion_done = False
        self._enrichment_precache_done = False
        self._pre_market_done = False

        # Between-scan scoring
        self._scorer = GuardedScorer()
        self._scoring_in_progress = False
        self._daily_scored = 0
        self._tg_last_update_id = 0

        # VRAM handoff flags
        self._vram_handoff_done = False
        self._morning_handoff_done = False

        # Pre-market pipeline flags
        self._premarket_features_done = False
        self._premarket_training_done = False
        self._premarket_news_done = False
        self._premarket_candidates_done = False
        self._ollama_warmup_done = False
        self._council_done = False

    def _reset_daily_state(self):
        """Reset daily flags at midnight ET."""
        self._morning_done = False
        self._eod_done = False
        self._last_scan_time = None
        self._daily_packets = []
        self._trades_managed_today = 0
        self._training_collection_done = False
        self._training_run_done = False
        self._saturday_reports_done = False
        self._daily_audit_done = False
        # Overnight flags
        self._post_close_done = False
        self._overnight_training_collection_done = False
        self._data_collection_done = False
        self._news_ingestion_done = False
        self._enrichment_precache_done = False
        self._pre_market_done = False
        # Scoring + VRAM handoffs
        self._daily_scored = 0
        self._vram_handoff_done = False
        self._morning_handoff_done = False
        # Pre-market pipeline
        self._premarket_features_done = False
        self._premarket_training_done = False
        self._premarket_news_done = False
        self._premarket_candidates_done = False
        self._ollama_warmup_done = False
        self._council_done = False

    def _is_market_open(self, now: datetime) -> bool:
        """Check if market is currently open (weekday, between open and close)."""
        if now.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        market_open = now.replace(hour=self.market_open_hour,
                                  minute=self.market_open_minute, second=0)
        market_close = now.replace(hour=self.market_close_hour,
                                   minute=0, second=0)
        return market_open <= now < market_close

    def _should_scan(self, now: datetime) -> bool:
        """Check if enough time has passed since last scan."""
        if not self._is_market_open(now):
            return False
        if self._last_scan_time is None:
            return True
        elapsed = (now - self._last_scan_time).total_seconds() / 60
        return elapsed >= self.scan_interval

    def _print_banner(self):
        """Print the startup banner."""
        now = datetime.now(ET)
        llm_status = "connected" if is_llm_available() else "not available"
        shadow_cfg = self.config.get("shadow_trading", {})
        shadow_status = "enabled" if shadow_cfg.get("enabled", False) else "disabled"

        bootcamp_str = (f"enabled (Phase {self.bootcamp_phase})"
                        if self.bootcamp_enabled else "disabled")

        from src.training.versioning import get_active_model_name, get_training_example_counts
        model_name = get_active_model_name()

        # Warn if config model differs from the active trained model
        config_model = self.config.get("llm", {}).get("model", "qwen3:8b")
        if model_name and model_name != "base" and model_name != config_model:
            logger.warning(
                "Config model is '%s' but active trained model is '%s' — "
                "inference will use the trained model",
                config_model, model_name,
            )

        if self.training_enabled:
            t_counts = get_training_example_counts()
            training_str = f"enabled ({t_counts['total']} examples)"
        else:
            training_str = "disabled"

        print(f"""
{'='*45}
 HALCYON LAB - WATCH MODE
{'='*45}
 Time: {now.strftime('%Y-%m-%d %H:%M:%S')} ET
 LLM: {llm_status}
 Model Version: {model_name}
 Shadow Trading: {shadow_status}
 Email Mode: {self.email_mode}
 Bootcamp: {bootcamp_str}
 Training: {training_str}

 Schedule:
   Morning watchlist: {self.morning_hour}:00 ET
   Market scans: every {self.scan_interval} min ({self.market_open_hour}:{self.market_open_minute:02d}-{self.market_close_hour}:00 ET)
   EOD recap: {self.eod_hour}:00 ET
   Overnight: {'enabled' if self.overnight else 'disabled'}

 Compute Schedule:
   Between-scan scoring: enabled (guard={self._scorer.guard_minutes}min)
   Overnight training: {'enabled (6:50PM-5:15AM)' if self.overnight else 'disabled'}
   Pre-market inference: {'enabled (6:00-9:25AM)' if self.overnight else 'disabled'}
   VRAM handoff: {'enabled' if self.overnight else 'disabled'}
   Target utilization: {'73%' if self.overnight else '~3%'}

 Press Ctrl+C to stop.
{'='*45}
""")

        # Send Telegram startup notification
        try:
            from src.notifications.telegram import notify_system_event, is_telegram_enabled
            if is_telegram_enabled():
                notify_system_event(
                    "HALCYON LAB STARTED",
                    f"Model: {model_name}\nMode: {'Overnight' if self.overnight else 'Standard'}\nTraining: {training_str}"
                )
                print(" Telegram: connected ✓")
            else:
                print(" Telegram: not configured")
        except Exception:
            print(" Telegram: not configured")

    def _run_morning_watchlist(self):
        """Execute the morning watchlist pipeline."""
        from src.data_ingestion.market_data import fetch_ohlcv, fetch_spy_benchmark
        from src.features.engine import compute_all_features
        from src.llm.packet_writer import enhance_packet_with_llm
        from src.llm.watchlist_writer import generate_watchlist_narrative
        from src.packets.template import build_packet_from_features, render_packet
        from src.packets.watchlist import build_morning_watchlist
        from src.ranking.ranker import rank_universe, get_top_candidates
        from src.universe.sp100 import get_sp100_universe
        from src.email.notifier import send_email

        print("[WATCH] Running morning watchlist pipeline...")
        universe = get_sp100_universe()
        ohlcv = fetch_ohlcv(universe)
        spy = fetch_spy_benchmark()

        if spy.empty:
            print("[WATCH] ERROR: Could not fetch SPY benchmark. Skipping morning watchlist.")
            return

        features = compute_all_features(ohlcv, spy)

        # Enrich features with fundamental, insider, and macro data
        try:
            from src.data_enrichment.enricher import enrich_features
            features = enrich_features(features, self.config)
        except Exception as e:
            logger.warning("[WATCH] Data enrichment failed: %s", e)

        ranked = rank_universe(features)
        candidates = get_top_candidates(ranked)
        packet_worthy = candidates["packet_worthy"]
        watchlist = candidates["watchlist"]

        now = datetime.now(ET)
        date_str = now.strftime("%Y-%m-%d")

        narrative = generate_watchlist_narrative(packet_worthy, watchlist, self.config)
        body = build_morning_watchlist(watchlist, packet_worthy, date_str,
                                       narrative=narrative)
        print(body)

        if self.email_mode in ("full_stream", "daily_summary"):
            subject = f"[TRADE DESK] Morning Watchlist - {date_str}"
            send_email(subject, body)
            print("[WATCH] Morning watchlist email sent.")

        # Telegram watchlist notification — send packet-worthy (high-conviction) names
        try:
            from src.notifications.telegram import notify_watchlist, is_telegram_enabled
            if is_telegram_enabled():
                pw_tickers = [c["ticker"] for c in candidates.get("packet_worthy", [])]
                wl_count = len(candidates.get("watchlist", []))
                notify_watchlist(pw_tickers[:5], len(pw_tickers),
                                 watchlist_count=wl_count)
        except Exception:
            pass

    def _run_scan(self):
        """Execute a market-hours scan cycle."""
        from src.api.websocket import broadcast_sync
        from src.data_ingestion.market_data import fetch_ohlcv, fetch_spy_benchmark
        from src.features.engine import compute_all_features
        from src.journal.store import log_recommendation
        from src.llm.packet_writer import enhance_packet_with_llm, _build_feature_prompt
        from src.packets.template import build_packet_from_features, render_packet
        from src.training.versioning import get_active_model_name
        from src.ranking.ranker import rank_universe, get_top_candidates
        from src.universe.sp100 import get_sp100_universe
        from src.email.notifier import send_email

        print("[WATCH] Running market scan...")
        try:
            broadcast_sync("scan_started", {"time": datetime.now(ET).isoformat()})
        except Exception:
            pass
        universe = get_sp100_universe()
        ohlcv = fetch_ohlcv(universe)
        spy = fetch_spy_benchmark()

        if spy.empty:
            print("[WATCH] ERROR: Could not fetch SPY benchmark. Skipping scan.")
            return

        features = compute_all_features(ohlcv, spy)

        # Enrich features with fundamental, insider, and macro data
        try:
            from src.data_enrichment.enricher import enrich_features
            features = enrich_features(features, self.config)
        except Exception as e:
            logger.warning("[WATCH] Data enrichment failed: %s", e)

        ranked = rank_universe(features)
        candidates = get_top_candidates(ranked)
        packet_worthy = candidates["packet_worthy"]

        # Cap packets per scan to avoid bleeding into next scan window
        bootcamp_cfg = self.config.get("bootcamp", {})
        max_packets = bootcamp_cfg.get("max_packets_per_scan", 8)
        if len(packet_worthy) > max_packets:
            overflow = packet_worthy[max_packets:]
            packet_worthy = packet_worthy[:max_packets]
            print(f"[WATCH] Capped at {max_packets} packets "
                  f"({len(overflow)} deferred to next scan)")

        if not packet_worthy:
            print(f"[WATCH] No packet-worthy setups. {len(candidates['watchlist'])} on watchlist.")
            try:
                broadcast_sync("scan_complete", {"tickers_scanned": len(universe),
                                                 "packets": 0})
            except Exception:
                pass
            return

        print(f"[WATCH] Found {len(packet_worthy)} packet-worthy names.")

        for candidate in packet_worthy:
            ticker = candidate["ticker"]
            feat = candidate["features"]
            feat["_score"] = candidate["score"]

            packet = build_packet_from_features(ticker, feat, self.config)
            packet = enhance_packet_with_llm(packet, feat, self.config)
            enriched_prompt = _build_feature_prompt(packet, feat)
            rendered = render_packet(packet)

            model_ver = get_active_model_name()
            rec_id = log_recommendation(
                packet, feat, candidate["score"], candidate["qualification"],
                model_version=model_ver,
                enriched_prompt=enriched_prompt,
                llm_conviction=getattr(packet, 'llm_conviction', None),
            )
            print(f"  -> Logged {ticker}: {rec_id}")
            self._trades_managed_today += 1

            try:
                broadcast_sync("trade_opened", {"ticker": ticker, "side": "BUY",
                                                "score": candidate["score"]})
            except Exception:
                pass

            # Telegram notification
            try:
                from src.notifications.telegram import notify_trade_opened, is_telegram_enabled
                if is_telegram_enabled():
                    ps = packet.position_sizing
                    notify_trade_opened(
                        ticker, ps.entry_price, ps.stop_level, ps.target_1,
                        candidate["score"], ps.shares,
                        setup_type=feat.get("setup_type"),
                        setup_confidence=feat.get("setup_confidence"))
            except Exception:
                pass

            if self.email_mode == "full_stream":
                subject = f"[TRADE DESK] Action Packet - {ticker}"
                send_email(subject, rendered)
                print(f"  -> Email sent for {ticker}")
            elif self.email_mode == "daily_summary":
                self._daily_packets.append(rendered)

        try:
            broadcast_sync("scan_complete", {"tickers_scanned": len(universe),
                                             "packets": len(packet_worthy)})
        except Exception:
            pass

    def _run_eod_recap(self):
        """Execute the EOD recap pipeline."""
        from src.data_ingestion.market_data import fetch_ohlcv, fetch_spy_benchmark
        from src.features.engine import compute_all_features
        from src.journal.store import get_todays_recommendations
        from src.packets.eod_recap import build_eod_recap
        from src.ranking.ranker import rank_universe, get_top_candidates
        from src.universe.sp100 import get_sp100_universe
        from src.email.notifier import send_email

        print("[WATCH] Running EOD recap pipeline...")
        universe = get_sp100_universe()
        ohlcv = fetch_ohlcv(universe)
        spy = fetch_spy_benchmark()

        if spy.empty:
            print("[WATCH] ERROR: Could not fetch SPY benchmark. Skipping EOD recap.")
            return

        features = compute_all_features(ohlcv, spy)
        ranked = rank_universe(features)
        candidates = get_top_candidates(ranked)
        journal_entries = get_todays_recommendations()

        now = datetime.now(ET)
        date_str = now.strftime("%Y-%m-%d")

        body = build_eod_recap(candidates["packet_worthy"], candidates["watchlist"],
                               journal_entries, date_str)

        # Append daily summary buffer if in daily_summary mode
        if self.email_mode == "daily_summary" and self._daily_packets:
            body += "\n\n" + "=" * 60 + "\nDAILY PACKET SUMMARY\n" + "=" * 60 + "\n"
            body += "\n\n".join(self._daily_packets)

        print(body)

        subject = f"[TRADE DESK] EOD Recap - {date_str}"
        send_email(subject, body)
        print("[WATCH] EOD recap email sent.")

    def run(self):
        """Main watch loop. Checks every 60 seconds."""
        self._print_banner()

        try:
            while True:
                now = datetime.now(ET)

                # Reset daily state at midnight
                today = now.date()
                if self._today is not None and today != self._today:
                    self._reset_daily_state()
                    print(f"[WATCH] New day: {today}. Daily state reset.")
                self._today = today

                hour = now.hour
                time_str = now.strftime("%H:%M")

                # 0. Ollama warm-up (9:25 AM — before first scan)
                if (hour == 9 and now.minute >= 25 and now.minute < 30
                        and not self._ollama_warmup_done):
                    self._safe_run("Ollama warm-up", self._run_ollama_warmup)
                    self._ollama_warmup_done = True

                # 0.5. Daily AI Council (8:30 AM — after watchlist, before first scan)
                if (hour == 8 and now.minute >= 30 and not self._council_done):
                    self._safe_run("daily council", self._run_daily_council)
                    self._council_done = True

                # 1. Morning watchlist
                if hour == self.morning_hour and not self._morning_done:
                    self._safe_run("morning watchlist", self._run_morning_watchlist)
                    self._morning_done = True

                # 2. Market hours scan
                elif self._should_scan(now):
                    print(f"[WATCH] {time_str} ET -- market open, scanning...")
                    self._safe_run("scan", self._run_scan)
                    self._last_scan_time = now

                # 3. EOD recap
                elif hour == self.eod_hour and not self._eod_done:
                    self._safe_run("EOD recap", self._run_eod_recap)
                    self._eod_done = True

                # 4. Daily audit (4:15 PM ET)
                elif (hour == 16 and now.minute >= 15 and now.minute < 30
                      and not self._daily_audit_done):
                    self._safe_run("daily audit", self._run_daily_audit)
                    self._daily_audit_done = True
                    # Send daily scoring summary via Telegram
                    try:
                        from src.notifications.telegram import notify_scoring_summary, is_telegram_enabled
                        if is_telegram_enabled() and self._daily_scored > 0:
                            import sqlite3
                            with sqlite3.connect("ai_research_desk.sqlite3") as conn:
                                backlog = conn.execute(
                                    "SELECT COUNT(*) FROM training_examples WHERE quality_score IS NULL"
                                ).fetchone()[0]
                            notify_scoring_summary(self._daily_scored, backlog)
                    except Exception:
                        pass

                # 5. Training data collection (4:30 PM ET)
                elif (self.training_enabled and hour == 16 and now.minute >= 30
                      and not self._training_collection_done):
                    self._safe_run("training collection", self._run_training_collection)
                    self._training_collection_done = True

                # 5. Overnight training trigger (5:00 PM ET)
                elif (self.training_enabled and hour == 17
                      and not self._training_run_done):
                    self._safe_run("training check", self._run_training_check)
                    self._training_run_done = True

                # 6. Saturday training report (9 AM ET)
                elif (self.training_enabled and now.weekday() == 5
                      and hour == 9 and not self._saturday_reports_done):
                    self._safe_run("Saturday reports", self._run_saturday_reports)
                    self._saturday_reports_done = True

                # ── Overnight schedule (weekdays only, --overnight flag, NOT during market hours) ──
                elif self.overnight and now.weekday() < 5 and not self._is_market_open(now):
                    ran = False

                    # Morning VRAM handoff (5:15 AM) — kill training, reload Ollama
                    if (hour == 5 and now.minute >= 15
                            and not self._morning_handoff_done):
                        self._safe_run("morning VRAM handoff",
                                       self._run_morning_handoff)
                        self._morning_handoff_done = True
                        ran = True

                    elif hour == 17 and now.minute >= 30 and not self._post_close_done:
                        self._safe_run("post-close capture", self._run_post_close_capture)
                        self._post_close_done = True
                        ran = True
                    elif (hour == 18 and self.training_enabled
                          and not self._overnight_training_collection_done):
                        self._safe_run("overnight training collection",
                                       self._run_overnight_training_collection)
                        self._overnight_training_collection_done = True
                        ran = True

                    # Evening VRAM handoff (6:50 PM) — unload Ollama, launch training
                    elif (hour == 18 and now.minute >= 50
                          and not self._vram_handoff_done):
                        self._safe_run("evening VRAM handoff",
                                       self._run_evening_handoff)
                        self._vram_handoff_done = True
                        ran = True

                    # NOTE: 9:30 PM data collection, 10 PM news, 11 PM enrichment
                    # are CPU/network only — they run concurrently with GPU training
                    elif (hour == 21 and now.minute >= 30
                          and not self._data_collection_done):
                        self._safe_run("data collection", self._run_data_collection)
                        self._data_collection_done = True
                        ran = True
                    elif hour == 22 and not self._news_ingestion_done:
                        self._safe_run("news ingestion", self._run_news_ingestion)
                        self._news_ingestion_done = True
                        ran = True
                    elif hour == 23 and not self._enrichment_precache_done:
                        self._safe_run("enrichment precache", self._run_enrichment_precache)
                        self._enrichment_precache_done = True
                        ran = True
                    elif hour == 6 and not self._pre_market_done:
                        self._safe_run("pre-market refresh", self._run_pre_market_refresh)
                        self._pre_market_done = True
                        ran = True

                    # ── Pre-market inference tasks (6-9:25 AM) ──
                    elif (hour == 6 and now.minute >= 2
                          and not self._premarket_features_done):
                        self._safe_run("rolling features",
                                       self._run_premarket_rolling_features)
                        self._premarket_features_done = True
                        ran = True
                    elif hour == 7 and not self._premarket_training_done:
                        self._safe_run("premarket training gen",
                                       self._run_premarket_training)
                        self._premarket_training_done = True
                        ran = True
                    elif (hour == 8 and now.minute >= 2
                          and not self._premarket_news_done):
                        self._safe_run("premarket news scoring",
                                       self._run_premarket_news_scoring)
                        self._premarket_news_done = True
                        ran = True
                    elif (hour == 9 and now.minute < 25
                          and not self._premarket_candidates_done):
                        self._safe_run("premarket candidates",
                                       self._run_premarket_candidates)
                        self._premarket_candidates_done = True
                        ran = True

                    if not ran:
                        print(f"[WATCH] {time_str} ET -- overnight mode")

                # 7. Between-scan scoring (market hours only)
                if self._is_market_open(now) and self._scorer.is_scoring_window():
                    if not self._scoring_in_progress:
                        self._scoring_in_progress = True
                        try:
                            result = self._scorer.score_batch()
                            if result["scored"] > 0:
                                self._daily_scored += result["scored"]
                                print(f"[WATCH] Scored {result['scored']} examples "
                                      f"({result['remaining']} remaining, "
                                      f"stopped: {result['stopped_reason']})")
                        except Exception as e:
                            logger.debug("[WATCH] Scoring error: %s", e)
                        finally:
                            self._scoring_in_progress = False

                # 8. Status log
                if not (self._should_scan(now) or
                        (hour == self.morning_hour and not self._morning_done) or
                        (hour == self.eod_hour and not self._eod_done)):
                    if self._is_market_open(now):
                        scored_str = (f", {self._daily_scored} scored"
                                      if self._daily_scored > 0 else "")
                        print(f"[WATCH] {time_str} ET -- market open, next scan in "
                              f"{self._minutes_until_next_scan(now):.0f} min{scored_str}")
                    elif not (self.overnight and now.weekday() < 5):
                        print(f"[WATCH] {time_str} ET -- market closed")

                # 9. Poll Telegram commands
                try:
                    from src.notifications.telegram import (
                        poll_commands, handle_command, send_telegram, is_telegram_enabled
                    )
                    if is_telegram_enabled():
                        commands, self._tg_last_update_id = poll_commands(
                            self._tg_last_update_id
                        )
                        for cmd in commands:
                            response = handle_command(cmd["command"], cmd["args"])
                            send_telegram(response)
                except Exception:
                    pass

                time.sleep(60)

        except KeyboardInterrupt:
            print(f"\nShutting down watch mode...")
            print(f"Final shadow status:")
            print(f"  {self._trades_managed_today} trades managed today")
            print("Goodbye.")

    def _safe_run(self, name: str, func):
        """Run a function with error recovery."""
        import traceback
        try:
            if self._consecutive_errors >= 3:
                print(f"[WATCH] Cooldown: 3 consecutive errors, waiting 5 minutes...")
                time.sleep(300)
                self._consecutive_errors = 0
            func()
            self._consecutive_errors = 0
        except Exception as e:
            self._consecutive_errors += 1
            logger.error("[WATCH] Error in %s: %s", name, e)
            logger.error(traceback.format_exc())
            print(f"[WATCH] ERROR in {name}: {e} (error {self._consecutive_errors}/3)")

    def _run_daily_audit(self):
        """Run the daily auditor agent."""
        from src.evaluation.auditor import run_daily_audit, check_escalation
        from src.email.notifier import send_email

        print("[WATCH] Running daily audit...")
        audit = run_daily_audit()
        assessment = audit.get("overall_assessment", "green")
        summary = (audit.get("summary") or "")[:200]
        print(f"[WATCH] Audit: {assessment} — {summary}")

        # Check for escalation
        actions = check_escalation(audit)
        for action in actions:
            print(f"[WATCH] Escalation: {action['action']} ({action['severity']})")

        # Send alert if red or yellow
        if assessment == "red":
            subject = "[TRADE DESK] DAILY AUDIT — RED"
            send_email(subject, f"Assessment: RED\n\n{audit.get('summary', '')}")
        elif assessment == "yellow":
            logger.info("[AUDIT] Yellow assessment — included in EOD recap")

    def _run_training_collection(self):
        """Collect training data from closed trades."""
        from src.training.data_collector import collect_training_examples_from_closed_trades
        print("[WATCH] Running training data collection...")
        count = collect_training_examples_from_closed_trades()
        print(f"[WATCH] Training data collection: {count} new examples generated")

    def _run_training_check(self):
        """Check if fine-tuning should be triggered."""
        from src.training.trainer import should_train, run_fine_tune
        trigger, reason = should_train()
        if trigger:
            print(f"[WATCH] Training triggered: {reason}")
            result = run_fine_tune()
            if result:
                print(f"[WATCH] Training complete: {result['version_name']}")
            else:
                print("[WATCH] Training failed. Check logs.")
        else:
            print(f"[WATCH] Training not needed: {reason}")

    def _run_saturday_reports(self):
        """Generate and send Saturday training and CTO reports."""
        from src.training.report import generate_training_report
        from src.email.notifier import send_email

        # Training report
        print("[WATCH] Generating Saturday training report...")
        report = generate_training_report()
        print(report)
        subject = "[TRADE DESK] Weekly Training Report"
        send_email(subject, report)
        print("[WATCH] Training report email sent.")

        # Weekly deep audit
        try:
            from src.evaluation.auditor import run_weekly_audit
            print("[WATCH] Running weekly deep audit...")
            weekly = run_weekly_audit(days=7)
            print(f"[WATCH] Weekly audit: {weekly.get('overall_assessment', 'n/a')}")
        except Exception as e:
            logger.error("[WATCH] Weekly audit failed: %s", e)
            print(f"[WATCH] Weekly audit failed: {e}")

        # CTO performance report
        try:
            from src.evaluation.cto_report import generate_cto_report, format_cto_report
            print("[WATCH] Generating CTO performance report...")
            cto_data = generate_cto_report(days=7)
            cto_text = format_cto_report(cto_data)
            print(cto_text)
            cto_subject = f"[TRADE DESK] CTO Performance Report ({cto_data['report_period']['start']} to {cto_data['report_period']['end']})"
            send_email(cto_subject, cto_text)
            print("[WATCH] CTO report email sent.")
        except Exception as e:
            logger.error("[WATCH] CTO report failed: %s", e)
            print(f"[WATCH] CTO report failed: {e}")

    # ── Overnight Schedule Methods ────────────────────────────────────

    def _run_post_close_capture(self):
        """5:30 PM ET — Capture final closing prices, update MFE/MAE on open positions."""
        from src.api.websocket import broadcast_sync
        from src.data_ingestion.market_data import fetch_ohlcv, fetch_spy_benchmark
        from src.journal.store import get_open_shadow_trades, update_shadow_trade
        from src.universe.sp100 import get_sp100_universe

        try:
            broadcast_sync("overnight_task", {"task": "post_close_capture", "status": "started"})
        except Exception:
            pass

        logger.info("[OVERNIGHT] Running post-close capture...")
        print("[WATCH] Running post-close capture...")

        universe = get_sp100_universe()
        ohlcv = fetch_ohlcv(universe)
        count = len(ohlcv)
        print(f"[WATCH] Fetched closing data for {count} tickers")

        # Update MFE/MAE on open positions
        open_trades = get_open_shadow_trades()
        updated = 0
        for trade in open_trades:
            ticker = trade["ticker"]
            if ticker in ohlcv and not ohlcv[ticker].empty:
                try:
                    close_price = float(ohlcv[ticker].iloc[-1].get("close", 0))
                    entry = trade.get("actual_entry_price") or trade.get("entry_price", 0)
                    if entry and close_price:
                        pnl_pct = (close_price - entry) / entry * 100
                        current_mfe = trade.get("mfe_pct") or 0
                        current_mae = trade.get("mae_pct") or 0
                        new_mfe = max(current_mfe, pnl_pct)
                        new_mae = min(current_mae, pnl_pct)
                        update_shadow_trade(trade["trade_id"],
                                            {"mfe_pct": new_mfe, "mae_pct": new_mae})
                        updated += 1
                except Exception as e:
                    logger.warning("[OVERNIGHT] MFE/MAE update failed for %s: %s", ticker, e)

        # Log daily regime from SPY close
        spy = fetch_spy_benchmark()
        if not spy.empty:
            logger.info("[OVERNIGHT] SPY close: %.2f", spy.iloc[-1].get("close", 0))

        print(f"[WATCH] Post-close capture complete: {count} tickers, {updated} MFE/MAE updates")

        try:
            broadcast_sync("overnight_task", {"task": "post_close_capture", "status": "complete",
                                              "tickers_updated": count, "mfe_mae_updated": updated})
        except Exception:
            pass

    def _run_overnight_training_collection(self):
        """6:00 PM ET — Collect training examples from today's closed trades."""
        from src.api.websocket import broadcast_sync
        from src.training.data_collector import collect_training_examples_from_closed_trades

        try:
            broadcast_sync("overnight_task", {"task": "training_collection", "status": "started"})
        except Exception:
            pass

        logger.info("[OVERNIGHT] Running training data collection...")
        print("[WATCH] Running overnight training data collection...")
        count = collect_training_examples_from_closed_trades()
        print(f"[WATCH] Training collection: {count} new examples")

        try:
            broadcast_sync("overnight_task", {"task": "training_collection", "status": "complete",
                                              "examples_collected": count})
        except Exception:
            pass

    def _run_news_ingestion(self):
        """10:00 PM ET — Full universe news pull and caching."""
        from src.api.websocket import broadcast_sync
        from src.universe.sp100 import get_sp100_universe

        try:
            broadcast_sync("overnight_task", {"task": "news_ingestion", "status": "started"})
        except Exception:
            pass

        logger.info("[OVERNIGHT] Running news ingestion...")
        print("[WATCH] Running news ingestion...")

        universe = get_sp100_universe()
        articles_cached = 0

        for ticker in universe:
            try:
                from src.data_enrichment.news import fetch_recent_news
                result = fetch_recent_news(ticker, lookback_days=1)
                if result and result.get("articles"):
                    articles_cached += len(result["articles"])
            except Exception as e:
                logger.warning("[OVERNIGHT] News fetch failed for %s: %s", ticker, e)

        print(f"[WATCH] News ingestion complete: {len(universe)} tickers, {articles_cached} articles cached")

        try:
            broadcast_sync("overnight_task", {"task": "news_ingestion", "status": "complete",
                                              "tickers_scanned": len(universe), "articles_cached": articles_cached})
        except Exception:
            pass

    def _run_enrichment_precache(self):
        """11:00 PM ET — Pre-fetch fundamentals, insider data, macro for all tickers."""
        from src.api.websocket import broadcast_sync
        from src.data_enrichment.enricher import enrich_features
        from src.universe.sp100 import get_sp100_universe

        try:
            broadcast_sync("overnight_task", {"task": "enrichment_precache", "status": "started"})
        except Exception:
            pass

        logger.info("[OVERNIGHT] Running enrichment pre-cache...")
        print("[WATCH] Running enrichment pre-cache...")

        universe = get_sp100_universe()
        # Build minimal feature dict just for cache warming
        stub_features = {t: {} for t in universe}
        try:
            enrich_features(stub_features, self.config)
            count = len(universe)
        except Exception as e:
            logger.error("[OVERNIGHT] Enrichment pre-cache failed: %s", e)
            count = 0

        print(f"[WATCH] Enrichment pre-cache complete: {count} tickers enriched")

        try:
            broadcast_sync("overnight_task", {"task": "enrichment_precache", "status": "complete",
                                              "tickers_enriched": count})
        except Exception:
            pass

    def _run_pre_market_refresh(self):
        """6:00 AM ET — Quick pre-market data check before morning watchlist."""
        from src.api.websocket import broadcast_sync
        from src.universe.sp100 import get_sp100_universe

        try:
            broadcast_sync("overnight_task", {"task": "pre_market_refresh", "status": "started"})
        except Exception:
            pass

        logger.info("[OVERNIGHT] Running pre-market refresh...")
        print("[WATCH] Running pre-market refresh...")

        universe = get_sp100_universe()
        # Fetch pre-market data if available (best-effort)
        try:
            from src.data_ingestion.market_data import fetch_ohlcv
            ohlcv = fetch_ohlcv(universe[:20])  # Quick check on top tickers
            print(f"[WATCH] Pre-market refresh: checked {len(ohlcv)} tickers")
        except Exception as e:
            logger.warning("[OVERNIGHT] Pre-market refresh failed: %s", e)
            print(f"[WATCH] Pre-market refresh: partial ({e})")

        try:
            broadcast_sync("overnight_task", {"task": "pre_market_refresh", "status": "complete"})
        except Exception:
            pass

    def _run_data_collection(self):
        """9:30 PM ET — Comprehensive market data collection."""
        from src.api.websocket import broadcast_sync
        from src.data_collection.options_collector import collect_options_chains
        from src.data_collection.options_metrics import compute_options_metrics
        from src.data_collection.vix_collector import collect_vix_term_structure
        from src.data_collection.trends_collector import collect_google_trends
        from src.data_collection.macro_collector import collect_macro_snapshots
        from src.data_collection.cboe_collector import collect_cboe_ratios
        from src.universe.sp100 import get_sp100_universe

        try:
            broadcast_sync("overnight_task", {"task": "data_collection", "status": "started"})
        except Exception:
            pass

        logger.info("[OVERNIGHT] Running comprehensive data collection...")
        print("[WATCH] Running comprehensive data collection...")

        universe = get_sp100_universe()
        results = {}

        # 1. Options chains (most important)
        print("[WATCH]   [1/7] Options chains...")
        results["options"] = collect_options_chains(universe)

        # 2. Derived metrics from chains
        print("[WATCH]   [2/7] Options metrics...")
        results["metrics"] = compute_options_metrics(universe)

        # 3. VIX term structure
        print("[WATCH]   [3/7] VIX term structure...")
        results["vix"] = collect_vix_term_structure()

        # 4. CBOE ratios
        print("[WATCH]   [4/7] CBOE ratios...")
        results["cboe"] = collect_cboe_ratios()

        # 5. FRED macro
        print("[WATCH]   [5/7] FRED macro indicators...")
        results["macro"] = collect_macro_snapshots()

        # 6. Google Trends (batched — subset each night)
        print("[WATCH]   [6/7] Google Trends (batch)...")
        results["trends"] = collect_google_trends(universe, batch_size=20)

        # 7. Earnings calendar
        print("[WATCH]   [7/7] Earnings calendar...")
        try:
            from scripts.fetch_earnings_calendar import fetch_earnings_dates
            results["earnings"] = fetch_earnings_dates(universe)
            upcoming = results["earnings"].get("upcoming_7d", [])
            if upcoming:
                logger.warning("[EARNINGS] %d stocks report this week: %s",
                               len(upcoming), ", ".join(upcoming))
                # Telegram earnings warning
                try:
                    from src.notifications.telegram import notify_earnings_warning, is_telegram_enabled
                    if is_telegram_enabled():
                        notify_earnings_warning(upcoming)
                except Exception:
                    pass
        except Exception as e:
            logger.debug("[WATCH] Earnings fetch failed: %s", e)
            results["earnings"] = {"error": str(e)}

        summary = {k: str(v) for k, v in results.items()}
        print(f"[WATCH] Data collection complete: {summary}")

        # Telegram overnight summary
        try:
            from src.notifications.telegram import notify_overnight_complete, is_telegram_enabled
            if is_telegram_enabled():
                notify_overnight_complete(results)
        except Exception:
            pass

        try:
            broadcast_sync("overnight_task", {"task": "data_collection", "status": "complete",
                                              "results": summary})
        except Exception:
            pass

    def _minutes_until_next_scan(self, now: datetime) -> float:
        """Calculate minutes until next scan is due."""
        if self._last_scan_time is None:
            return 0
        elapsed = (now - self._last_scan_time).total_seconds() / 60
        return max(0, self.scan_interval - elapsed)

    # ── VRAM Handoff Methods ─────────────────────────────────────────

    def _run_evening_handoff(self):
        """6:50 PM ET — Unload Ollama, launch overnight training subprocess."""
        from pathlib import Path
        from src.scheduler.vram_manager import VRAMManager

        vm = VRAMManager()
        if vm.handoff_to_training():
            vm.launch_training_subprocess(
                "overnight",
                ["-m", "scripts.overnight_train"],
            )
            self._vram_manager = vm
            print("[WATCH] VRAM handoff complete — overnight training started")
            try:
                from src.notifications.telegram import notify_vram_handoff, is_telegram_enabled
                if is_telegram_enabled():
                    notify_vram_handoff("training", True)
            except Exception:
                pass
        else:
            print("[WATCH] VRAM handoff FAILED — staying in inference mode")
            try:
                from src.notifications.telegram import notify_vram_handoff, is_telegram_enabled
                if is_telegram_enabled():
                    notify_vram_handoff("training", False, "Staying in inference mode")
            except Exception:
                pass

    def _run_morning_handoff(self):
        """5:15 AM ET — Kill training subprocess, reload Ollama."""
        from pathlib import Path
        from src.scheduler.vram_manager import VRAMManager

        # Signal overnight pipeline to stop
        stop_flag = Path("data/STOP_OVERNIGHT")
        stop_flag.parent.mkdir(parents=True, exist_ok=True)
        stop_flag.touch()

        # Give subprocess time to checkpoint and exit
        time.sleep(60)

        vm = getattr(self, '_vram_manager', None) or VRAMManager()
        if vm.handoff_to_inference():
            stop_flag.unlink(missing_ok=True)
            print("[WATCH] Morning handoff complete — Ollama loaded and warm")
            try:
                from src.notifications.telegram import notify_vram_handoff, is_telegram_enabled
                if is_telegram_enabled():
                    notify_vram_handoff("inference", True)
            except Exception:
                pass
        else:
            print("[WATCH] Morning handoff FAILED — attempting Ollama restart")
            try:
                from src.notifications.telegram import notify_vram_handoff, is_telegram_enabled
                if is_telegram_enabled():
                    notify_vram_handoff("inference", False, "Attempting restart")
            except Exception:
                pass
            # Fallback: try reload anyway
            stop_flag.unlink(missing_ok=True)
            try:
                vm._reload_ollama()
            except Exception as e:
                logger.error("[WATCH] Ollama restart failed: %s", e)

    # ── AI Council ────────────────────────────────────────────────

    def _run_daily_council(self):
        """8:30 AM ET — Run the daily AI Council session."""
        print("[WATCH] Running daily AI Council session...")
        try:
            from src.council.engine import CouncilEngine
            engine = CouncilEngine()
            result = engine.run_session(session_type="daily")
            consensus = result.get("consensus", "unknown")
            cost = result.get("total_cost", 0)
            rounds = result.get("rounds_completed", 0)
            contested = result.get("is_contested", False)
            print(f"[WATCH] Council complete: {consensus} "
                  f"({'CONTESTED' if contested else 'agreed'}) "
                  f"({rounds} rounds, ${cost:.2f})")

            # Telegram notification
            try:
                from src.notifications.telegram import send_telegram, is_telegram_enabled
                if is_telegram_enabled():
                    now = datetime.now(ET).strftime("%H:%M ET")
                    msg = f"🏛️ <b>AI COUNCIL SESSION</b> ({now})\n"
                    msg += f"Consensus: <b>{consensus.upper()}</b>"
                    if contested:
                        msg += " ⚠️ CONTESTED"
                    msg += f"\nCost: ${cost:.2f} | Rounds: {rounds}"
                    send_telegram(msg)
            except Exception:
                pass
        except Exception as e:
            logger.error("[WATCH] Council session failed: %s", e)
            print(f"[WATCH] Council session failed: {e}")

    # ── Ollama Warm-Up ─────────────────────────────────────────────

    def _run_ollama_warmup(self):
        """9:25 AM ET — Full-length warm-up inference before first scan.

        Not just a health check — runs a real prompt of similar length to
        what the scan will generate, warming up the KV cache and CUDA kernels.
        """
        from pathlib import Path
        from src.llm.client import generate, is_llm_available

        if not is_llm_available():
            print("[WATCH] Ollama not available — skipping warm-up")
            return

        warmup_path = Path("data/reference/warmup_prompt.txt")
        if warmup_path.exists():
            warmup_prompt = warmup_path.read_text(encoding="utf-8")
        else:
            warmup_prompt = (
                "Analyze a hypothetical pullback trade in AAPL at $195.00. "
                "The stock has pulled back 6% from its 50-day high in a strong uptrend. "
                "SMA50 is rising, price is 3% above SMA200. Volume is contracting on "
                "the pullback (0.7x average). RSI is at 42. The broader market regime "
                "is calm_uptrend with healthy breadth (68% above 50d MA). "
                "Provide conviction (1-10), why_now analysis, and deeper analysis."
            )

        import time as _time
        start = _time.time()
        system_prompt = "You are a senior equity research analyst. Analyze the setup."
        result = generate(warmup_prompt, system_prompt)
        elapsed = _time.time() - start

        if result:
            print(f"[WATCH] Ollama warm-up complete — {elapsed:.1f}s — ready for first scan")
        else:
            print(f"[WATCH] WARNING: Ollama warm-up failed ({elapsed:.1f}s) — "
                  "first scan may be slow")

    # ── Pre-Market Pipeline Methods ──────────────────────────────────

    def _run_premarket_rolling_features(self):
        """6:02 AM ET — Pre-compute rolling features for faster scans."""
        from src.scheduler.premarket import PreMarketPipeline
        pipeline = PreMarketPipeline()
        result = pipeline.run_rolling_features()
        print(f"[WATCH] Rolling features: {result['computed']} computed")

    def _run_premarket_training(self):
        """7:00 AM ET — Verify Ollama + generate self-blinded training data."""
        from src.scheduler.premarket import PreMarketPipeline
        pipeline = PreMarketPipeline()
        if not pipeline.verify_ollama_warm():
            print("[WATCH] Ollama not warm — skipping training generation")
            return
        result = pipeline.run_training_generation()
        print(f"[WATCH] Premarket training: {result['generated']} generated, "
              f"{result['unscored']} unscored")

    def _run_premarket_news_scoring(self):
        """8:02 AM ET — Score overnight news for market impact."""
        from src.scheduler.premarket import PreMarketPipeline
        pipeline = PreMarketPipeline()
        result = pipeline.run_news_scoring()
        print(f"[WATCH] News scoring: {result['scored']} articles scored")

    def _run_premarket_candidates(self):
        """9:00 AM ET — Pre-analyze candidates for first scan."""
        from src.scheduler.premarket import PreMarketPipeline
        pipeline = PreMarketPipeline()
        result = pipeline.run_candidate_analysis()
        print(f"[WATCH] Pre-analyzed {result['count']} candidates")
