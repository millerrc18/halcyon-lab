"""Watch loop for automated daily cadence.

Simple Python loop — no APScheduler or cron dependencies.
"""

import time
import logging
from datetime import datetime, date
from zoneinfo import ZoneInfo

from src.config import load_config
from src.llm.client import is_llm_available

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")


class WatchLoop:
    """Automated daily cadence loop for the AI Research Desk."""

    def __init__(self, config: dict, email_mode: str | None = None):
        self.config = config
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

 Press Ctrl+C to stop.
{'='*45}
""")

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

    def _run_scan(self):
        """Execute a market-hours scan cycle."""
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

        if not packet_worthy:
            print(f"[WATCH] No packet-worthy setups. {len(candidates['watchlist'])} on watchlist.")
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

            if self.email_mode == "full_stream":
                subject = f"[TRADE DESK] Action Packet - {ticker}"
                send_email(subject, rendered)
                print(f"  -> Email sent for {ticker}")
            elif self.email_mode == "daily_summary":
                self._daily_packets.append(rendered)

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

                # 7. Status log
                else:
                    if self._is_market_open(now):
                        print(f"[WATCH] {time_str} ET -- market open, next scan in "
                              f"{self._minutes_until_next_scan(now):.0f} min")
                    else:
                        print(f"[WATCH] {time_str} ET -- market closed")

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

    def _minutes_until_next_scan(self, now: datetime) -> float:
        """Calculate minutes until next scan is due."""
        if self._last_scan_time is None:
            return 0
        elapsed = (now - self._last_scan_time).total_seconds() / 60
        return max(0, self.scan_interval - elapsed)
