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

        # Expanded notification flags
        self._premarket_brief_done = False
        self._first_scan_done = False
        self._eod_report_done = False
        self._data_asset_report_done = False
        self._weekly_digest_done = False
        self._last_vix_alert_level: float | None = None
        self._earnings_warning_done = False

        # Research synthesis + daily metrics
        self._research_synthesis_done = False
        self._daily_metric_snapshot_done = False

        # Collector failure tracking: {collector_name: consecutive_failure_count}
        self._collector_failures: dict[str, int] = {}

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
        # Expanded notification flags
        self._premarket_brief_done = False
        self._first_scan_done = False
        self._eod_report_done = False
        self._data_asset_report_done = False
        self._weekly_digest_done = False
        self._earnings_warning_done = False
        # Research + metrics
        self._research_synthesis_done = False
        self._daily_metric_snapshot_done = False

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

            # ═══ SHADOW TRADE EXECUTION (enables the training flywheel) ═══
            try:
                from src.shadow_trading.executor import open_shadow_trade
                trade_id = open_shadow_trade(rec_id, packet, feat)
                if trade_id:
                    print(f"  -> Shadow trade opened: {trade_id}")
                else:
                    print(f"  -> Shadow trade skipped (risk governor or position limit)")
            except Exception as e:
                logger.warning("[WATCH] Shadow trade failed for %s: %s", ticker, e)

            # ═══ LIVE TRADE EXECUTION (dual execution if enabled) ═══
            live_cfg = self.config.get("live_trading", {})
            now_live = datetime.now(ET)
            hour_live = now_live.hour
            if (live_cfg.get("enabled", False)
                    and getattr(packet, 'llm_conviction', None) is not None
                    and not (hour_live == 9 and now_live.minute < 31)):  # Skip first scan
                try:
                    from src.shadow_trading.executor import open_live_trade
                    live_id = open_live_trade(rec_id, packet, feat)
                    if live_id:
                        print(f"  -> LIVE trade opened: {live_id}")
                except Exception as e:
                    logger.warning("[WATCH] Live trade failed for %s: %s", ticker, e)

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

        # Manage existing open trades (stop/target/timeout exits)
        try:
            from src.shadow_trading.executor import check_and_manage_open_trades
            actions = check_and_manage_open_trades()
            for action in actions:
                action_type = action.get("type", action.get("action", "unknown"))
                print(f"  -> Trade action: {action.get('ticker', '?')} — {action_type} "
                      f"(P&L: ${action.get('pnl_dollars', 0):+.2f})")
        except Exception as e:
            logger.warning("[WATCH] Trade management failed: %s", e)

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

    @staticmethod
    def _ensure_all_tables():
        """Create all expected SQLite tables on startup to prevent missing-table errors."""
        import sqlite3
        db_path = "ai_research_desk.sqlite3"
        tables = [
            """CREATE TABLE IF NOT EXISTS council_sessions (
                session_id TEXT PRIMARY KEY, session_type TEXT NOT NULL,
                trigger_reason TEXT, created_at TEXT NOT NULL, consensus TEXT,
                confidence_weighted_score REAL, is_contested INTEGER DEFAULT 0,
                total_cost REAL, rounds_completed INTEGER DEFAULT 0)""",
            """CREATE TABLE IF NOT EXISTS council_votes (
                vote_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, agent_name TEXT NOT NULL,
                round INTEGER NOT NULL, position TEXT, confidence INTEGER,
                recommendation TEXT, key_data_points TEXT, risk_flags TEXT,
                vote TEXT, is_devils_advocate INTEGER DEFAULT 0)""",
            """CREATE TABLE IF NOT EXISTS schedule_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT, metric_date TEXT,
                metric_name TEXT, metric_value REAL, details TEXT)""",
            """CREATE TABLE IF NOT EXISTS setup_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT, scan_date TEXT,
                setup_type TEXT, confidence REAL, features_json TEXT, created_at TEXT)""",
            """CREATE TABLE IF NOT EXISTS canary_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT, model_version TEXT,
                perplexity REAL, distinct_2 REAL, verdict TEXT, details TEXT, created_at TEXT)""",
            """CREATE TABLE IF NOT EXISTS quality_drift_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT, metric_date TEXT,
                avg_score REAL, score_std REAL, pass_rate REAL,
                template_fallback_rate REAL, created_at TEXT)""",
            """CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT,
                detail TEXT, created_at TEXT)""",
            """CREATE TABLE IF NOT EXISTS api_costs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, model TEXT, purpose TEXT,
                input_tokens INTEGER, output_tokens INTEGER,
                estimated_cost REAL, created_at TEXT)""",
            """CREATE TABLE IF NOT EXISTS training_examples (
                id INTEGER PRIMARY KEY AUTOINCREMENT, example_id TEXT UNIQUE,
                ticker TEXT, trade_date TEXT, input_text TEXT, output_text TEXT,
                quality_score REAL, curriculum_stage TEXT, outcome TEXT,
                source TEXT, model_version TEXT, created_at TEXT)""",
            """CREATE TABLE IF NOT EXISTS research_papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL,
                external_id TEXT UNIQUE, title TEXT NOT NULL, authors TEXT,
                abstract TEXT, url TEXT NOT NULL, published_date TEXT,
                categories TEXT, relevance_score REAL, relevance_reason TEXT,
                full_text TEXT, actionable INTEGER DEFAULT 0,
                action_taken TEXT, collected_at TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS research_digests (
                id INTEGER PRIMARY KEY AUTOINCREMENT, week_start TEXT NOT NULL,
                week_end TEXT NOT NULL, papers_reviewed INTEGER,
                actionable_count INTEGER, digest_text TEXT, threats TEXT,
                opportunities TEXT, created_at TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS scan_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT, scan_number INTEGER,
                scan_time TEXT, universe_count INTEGER, features_count INTEGER,
                scored_count INTEGER, packet_worthy INTEGER, risk_passed INTEGER,
                paper_traded INTEGER, live_traded INTEGER, llm_success INTEGER,
                llm_total INTEGER, llm_fallback INTEGER, avg_conviction REAL,
                duration_seconds REAL, created_at TEXT)""",
            # Tables created by data collectors that sync needs
            """CREATE TABLE IF NOT EXISTS short_interest (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT NOT NULL,
                settlement_date TEXT, short_interest INTEGER, avg_daily_volume INTEGER,
                days_to_cover REAL, short_pct_float REAL, source TEXT,
                collected_at TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS edgar_filings (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT NOT NULL,
                cik TEXT NOT NULL, form_type TEXT NOT NULL, filing_date TEXT NOT NULL,
                accession_number TEXT UNIQUE NOT NULL, filing_url TEXT,
                description TEXT, full_text TEXT, sections_json TEXT,
                word_count INTEGER, collected_at TEXT NOT NULL,
                sentiment_polarity REAL, sentiment_negative_count INTEGER,
                sentiment_uncertainty_count INTEGER, cautionary_phrases TEXT,
                sentiment_delta_polarity REAL)""",
            """CREATE TABLE IF NOT EXISTS insider_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT NOT NULL,
                insider_name TEXT, title TEXT, transaction_type TEXT,
                shares INTEGER, price REAL, value REAL, transaction_date TEXT,
                ownership_type TEXT, source TEXT, collected_at TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS fed_communications (
                id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL,
                event_date TEXT NOT NULL, title TEXT, summary TEXT,
                sentiment TEXT, key_phrases TEXT, url TEXT,
                source TEXT, collected_at TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS analyst_estimates (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT NOT NULL,
                metric TEXT, period TEXT, estimate REAL, actual REAL,
                surprise REAL, surprise_pct REAL, num_analysts INTEGER,
                source TEXT, collected_at TEXT NOT NULL)""",
        ]
        # Slippage columns on shadow_trades
        slippage_cols = [
            ("signal_entry_price", "REAL"), ("fill_entry_price", "REAL"),
            ("entry_slippage_bps", "REAL"), ("signal_exit_price", "REAL"),
            ("fill_exit_price", "REAL"), ("exit_slippage_bps", "REAL"),
        ]
        # NLP columns on edgar_filings (for existing DBs)
        edgar_nlp_cols = [
            ("sentiment_polarity", "REAL"), ("sentiment_negative_count", "INTEGER"),
            ("sentiment_uncertainty_count", "INTEGER"), ("cautionary_phrases", "TEXT"),
            ("sentiment_delta_polarity", "REAL"),
        ]
        try:
            with sqlite3.connect(db_path) as conn:
                for ddl in tables:
                    conn.execute(ddl)
                for col, typ in slippage_cols:
                    try:
                        conn.execute(f"ALTER TABLE shadow_trades ADD COLUMN {col} {typ}")
                    except Exception:
                        pass  # Column already exists
                for col, typ in edgar_nlp_cols:
                    try:
                        conn.execute(f"ALTER TABLE edgar_filings ADD COLUMN {col} {typ}")
                    except Exception:
                        pass  # Column already exists
            logger.info("[WATCH] All SQLite tables verified/created")
        except Exception as exc:
            logger.warning("[WATCH] Table creation error: %s", exc)

    @staticmethod
    def _configure_database():
        """Configure SQLite for production use."""
        import sqlite3
        try:
            conn = sqlite3.connect("ai_research_desk.sqlite3")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.close()
            logger.info("[DB] SQLite configured: WAL mode, synchronous=NORMAL, busy_timeout=5000ms")
        except Exception as exc:
            logger.warning("[DB] SQLite configuration failed: %s", exc)

    def _backup_database(self):
        """Create a daily backup of the SQLite database using the Online Backup API."""
        import sqlite3
        from pathlib import Path

        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)

        backup_path = backup_dir / f"halcyon_{datetime.now(ET).strftime('%Y%m%d')}.sqlite3"
        try:
            src = sqlite3.connect("ai_research_desk.sqlite3")
            dst = sqlite3.connect(str(backup_path))
            src.backup(dst)
            dst.close()
            src.close()

            # Prune old backups (keep last 7)
            backups = sorted(backup_dir.glob("halcyon_*.sqlite3"))
            for old in backups[:-7]:
                old.unlink()

            logger.info("[DB] Backup created: %s", backup_path.name)
        except Exception as exc:
            logger.warning("[DB] Backup failed: %s", exc)

    def run(self):
        """Main watch loop. Checks every 60 seconds."""
        self._print_banner()

        # Ensure all expected tables exist
        self._ensure_all_tables()

        # Configure SQLite for production use (WAL mode)
        self._configure_database()

        # Validate starting capital
        capital = self.config.get("risk", {}).get("starting_capital", 0)
        if capital < 10000:
            logger.warning("[WATCH] ⚠️ starting_capital is $%d — this seems low for paper trading. Expected $100,000.", capital)
            print(f" ⚠️ WARNING: starting_capital is ${capital:,} — expected $100,000 for paper trading")

        # Start Render cloud sync background thread
        try:
            from src.sync.render_sync import start_render_sync
            sync_thread = start_render_sync(self.config)
            if sync_thread:
                print(" Render sync: enabled ✓")
            else:
                print(" Render sync: disabled")
        except Exception as e:
            logger.debug("Render sync startup failed: %s", e)
            print(f" Render sync: error ({e})")

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
                    # 1E. Check VIX regime alert after each scan
                    self._safe_run("VIX regime check", self._check_vix_regime_alert)

                # 3. EOD recap
                elif hour == self.eod_hour and not self._eod_done:
                    self._safe_run("EOD recap", self._run_eod_recap)
                    self._eod_done = True
                    # H2. Daily metric snapshot (every trading day, not just Saturday)
                    if not self._daily_metric_snapshot_done:
                        self._safe_run("daily metric snapshot", self._save_daily_metric_snapshot)
                        self._daily_metric_snapshot_done = True
                    # 1C. EOD P&L report via Telegram
                    if not self._eod_report_done:
                        self._safe_run("EOD Telegram report", self._send_eod_report)
                        self._eod_report_done = True

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
                    # 1D. Data asset report after training collection
                    if not self._data_asset_report_done:
                        self._safe_run("data asset report", self._send_data_asset_report)
                        self._data_asset_report_done = True

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

                # H1. Research synthesis (Sunday 6 PM ET)
                elif (now.weekday() == 6 and hour == 18
                      and not self._research_synthesis_done):
                    self._safe_run("research synthesis", self._run_research_synthesis)
                    self._research_synthesis_done = True

                # 1H. Weekly digest (Sunday 8 PM ET)
                elif (now.weekday() == 6 and hour == 20
                      and not self._weekly_digest_done):
                    self._safe_run("weekly digest", self._send_weekly_digest)
                    self._weekly_digest_done = True

                # 1L. Earnings proximity warning (8:00 AM weekdays)
                if (hour == 8 and now.minute < 5 and now.weekday() < 5
                        and not self._earnings_warning_done):
                    self._safe_run("earnings proximity", self._check_earnings_proximity)
                    self._earnings_warning_done = True

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

                        # 1A. Pre-market brief (right after pre-market refresh at 6:00 AM)
                        if not self._premarket_brief_done:
                            self._safe_run("pre-market brief", self._send_premarket_brief)
                            self._premarket_brief_done = True

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

        # CUSUM performance change detection
        try:
            from src.evaluation.change_detector import detect_performance_change
            change = detect_performance_change()
            if change and change.get("alarm"):
                alarm_msg = f"[CUSUM] Performance change detected: {change.get('direction', 'negative')} shift"
                logger.warning(alarm_msg)
                print(f"[WATCH] {alarm_msg}")
                try:
                    from src.notifications.telegram import send_telegram_message
                    send_telegram_message(f"⚠️ CUSUM ALARM\n{alarm_msg}\nDetails: {change.get('detail', '')}")
                except Exception:
                    pass
        except Exception as e:
            logger.debug("[AUDIT] CUSUM check failed: %s", e)

        # Leakage detection
        try:
            from src.training.leakage_detector import run_leakage_check
            leakage = run_leakage_check()
            if leakage and leakage.get("balanced_accuracy", 0) > 0.65:
                leak_msg = f"[LEAKAGE] Balanced accuracy {leakage['balanced_accuracy']:.1%} > 65% threshold"
                logger.warning(leak_msg)
                try:
                    from src.notifications.telegram import send_telegram_message
                    send_telegram_message(f"🔴 LEAKAGE ALERT\n{leak_msg}")
                except Exception:
                    pass
        except ImportError:
            pass
        except Exception as e:
            logger.debug("[AUDIT] Leakage check failed: %s", e)

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

        # Log daily regime from SPY close (with retry and fallback)
        spy = fetch_spy_benchmark()
        spy_close = spy.iloc[-1].get("close", 0) if not spy.empty else 0
        if spy_close == 0:
            import time as _time
            logger.info("[OVERNIGHT] SPY close returned $0, retrying in 5 minutes...")
            _time.sleep(300)
            spy = fetch_spy_benchmark()
            spy_close = spy.iloc[-1].get("close", 0) if not spy.empty else 0
        if spy_close == 0 and "SPY" in ohlcv and not ohlcv["SPY"].empty:
            spy_close = float(ohlcv["SPY"].iloc[-1].get("close", 0))
            logger.info("[OVERNIGHT] SPY close from OHLCV fallback: %.2f", spy_close)
        if spy_close > 0:
            logger.info("[OVERNIGHT] SPY close: %.2f", spy_close)
        else:
            logger.warning("[OVERNIGHT] SPY close unavailable")

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
        now = datetime.now(ET)
        results = {}

        # 1. Options chains (most important)
        print("[WATCH]   [1/12] Options chains...")
        results["options"] = collect_options_chains(universe)

        # 2. Derived metrics from chains
        print("[WATCH]   [2/12] Options metrics...")
        results["metrics"] = compute_options_metrics(universe)

        # 3. VIX term structure
        print("[WATCH]   [3/12] VIX term structure...")
        results["vix"] = collect_vix_term_structure()

        # 4. CBOE ratios
        print("[WATCH]   [4/12] CBOE ratios...")
        results["cboe"] = collect_cboe_ratios()

        # 5. FRED macro (35+ series)
        print("[WATCH]   [5/12] FRED macro indicators...")
        results["macro"] = collect_macro_snapshots()

        # 6. Google Trends (market-wide sentiment terms)
        print("[WATCH]   [6/12] Google Trends (sentiment)...")
        results["trends"] = collect_google_trends(universe, batch_size=20)

        # 7. Earnings calendar
        print("[WATCH]   [7/12] Earnings calendar...")
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

        # 8. SEC EDGAR filings (new filings only)
        print("[WATCH]   [8/12] SEC EDGAR filings...")
        try:
            from src.data_collection.edgar_collector import collect_new_filings
            results["edgar"] = collect_new_filings(universe)
        except Exception as e:
            logger.warning("[WATCH] EDGAR collection failed: %s", e)
            results["edgar"] = {"error": str(e)}

        # 9. Insider transactions
        print("[WATCH]   [9/12] Insider transactions...")
        try:
            from src.data_collection.insider_collector import collect_insider_transactions
            results["insider"] = collect_insider_transactions(universe)
        except Exception as e:
            logger.warning("[WATCH] Insider collection failed: %s", e)
            results["insider"] = {"error": str(e)}

        # 10. FINRA short interest (biweekly — around settlement dates)
        if now.day in (1, 2, 15, 16):
            print("[WATCH]   [10/12] Short interest...")
            try:
                from src.data_collection.short_interest_collector import collect_short_interest
                results["short_interest"] = collect_short_interest(universe)
            except Exception as e:
                logger.warning("[WATCH] Short interest collection failed: %s", e)
                results["short_interest"] = {"error": str(e)}
        else:
            results["short_interest"] = "skipped (not settlement date)"

        # 11. Fed communications
        print("[WATCH]   [11/12] Fed communications...")
        try:
            from src.data_collection.fed_collector import collect_fed_communications
            results["fed"] = collect_fed_communications()
        except Exception as e:
            logger.warning("[WATCH] Fed collection failed: %s", e)
            results["fed"] = {"error": str(e)}

        # 12. Analyst estimates (batch 20/night to stay under FMP limit)
        print("[WATCH]   [12/12] Analyst estimates (batch)...")
        try:
            from src.data_collection.analyst_collector import collect_analyst_estimates
            results["analyst"] = collect_analyst_estimates(universe, batch_size=20)
        except Exception as e:
            logger.warning("[WATCH] Analyst collection failed: %s", e)
            results["analyst"] = {"error": str(e)}

        # 13. Research papers
        print("[WATCH]   [13/13] Research papers...")
        try:
            from src.data_collection.research_collector import collect_research_papers
            research_results = collect_research_papers()
            results["research"] = research_results
            print(f"[WATCH]   [13/13] Research: {research_results.get('total_new', 0)} new papers "
                  f"(crawled {research_results.get('total_crawled', 0)})")
        except Exception as e:
            logger.warning("[COLLECTORS] Research collection failed: %s", e)
            results["research"] = {"error": str(e)}

        summary = {k: str(v) for k, v in results.items()}
        print(f"[WATCH] Data collection complete: {summary}")

        # Log collection results to activity log
        try:
            from src.utils.activity_logger import log_activity, DATA_COLLECTION
            log_activity(DATA_COLLECTION, f"Overnight collection: {len(results)} collectors", results)
        except Exception:
            pass

        # 1J. Track collector failures and alert at 3+ consecutive
        try:
            from src.notifications.telegram import notify_collection_failure, is_telegram_enabled
            if is_telegram_enabled():
                for name, result in results.items():
                    is_error = (isinstance(result, str) and "error" in result.lower()) or \
                               (isinstance(result, dict) and "error" in str(result).lower())
                    if is_error:
                        self._collector_failures[name] = self._collector_failures.get(name, 0) + 1
                        if self._collector_failures[name] >= 3:
                            other_status = {
                                n: self._collector_failures.get(n, 0) < 3
                                for n in results if n != name
                            }
                            notify_collection_failure(
                                collector_name=name,
                                consecutive_failures=self._collector_failures[name],
                                last_error=str(result)[:80],
                                last_success_ago="unknown",
                                other_collectors=other_status,
                            )
                    else:
                        self._collector_failures[name] = 0  # Reset on success
        except Exception:
            pass

        # H3. Notify new research papers via Telegram
        if research_results.get("total_new", 0) > 0:
            try:
                from src.notifications.telegram import send_telegram, is_telegram_enabled
                if is_telegram_enabled():
                    import sqlite3 as _sq
                    with _sq.connect("ai_research_desk.sqlite3") as _cn:
                        top = _cn.execute(
                            "SELECT title, relevance_score FROM research_papers ORDER BY created_at DESC LIMIT 1"
                        ).fetchone()
                    top_title = top[0] if top else "Unknown"
                    top_score = top[1] if top else 0
                    send_telegram(
                        f"<b>NEW RESEARCH PAPERS</b>\n\n"
                        f"Papers found: {research_results['total_new']}\n"
                        f"Top paper: {top_title}\n"
                        f"Relevance: {top_score:.2f}"
                    )
            except Exception:
                pass

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

    # ── Expanded Notification Methods ────────────────────────────────

    def _send_premarket_brief(self):
        """6:00 AM ET — Send pre-market brief with overnight context."""
        import sqlite3
        from src.notifications.telegram import notify_premarket_brief, is_telegram_enabled
        if not is_telegram_enabled():
            return

        try:
            with sqlite3.connect("ai_research_desk.sqlite3") as conn:
                conn.row_factory = sqlite3.Row

                # VIX from vix_term_structure (latest)
                vix_row = conn.execute(
                    "SELECT vix FROM vix_term_structure ORDER BY collected_at DESC LIMIT 1"
                ).fetchone()
                vix = vix_row["vix"] if vix_row else 0.0

                vix_prev_row = conn.execute(
                    "SELECT vix FROM vix_term_structure ORDER BY collected_at DESC LIMIT 1 OFFSET 1"
                ).fetchone()
                vix_prev = vix_prev_row["vix"] if vix_prev_row else vix
                vix_change = vix - vix_prev

                # Regime from latest features
                from src.features.regime import classify_regime
                regime_data = {"vix_proxy": vix}
                regime = classify_regime(regime_data)

                # Earnings today
                today_str = datetime.now(ET).strftime("%Y-%m-%d")
                earnings_rows = conn.execute(
                    "SELECT ticker, earnings_time FROM earnings_calendar WHERE earnings_date = ?",
                    (today_str,),
                ).fetchall()
                earnings_today = []
                for r in earnings_rows:
                    time_label = ""
                    if r["earnings_time"]:
                        if "after" in (r["earnings_time"] or "").lower():
                            time_label = " (AMC)"
                        elif "before" in (r["earnings_time"] or "").lower():
                            time_label = " (BMO)"
                    earnings_today.append(f"{r['ticker']}{time_label}")

                # Event proximity from market_event_calendar.csv
                import csv
                from pathlib import Path
                fomc_days = None
                nfp_days = None
                cal_path = Path("data/reference/market_event_calendar.csv")
                if cal_path.exists():
                    now_date = datetime.now(ET).date()
                    with open(cal_path, encoding="utf-8") as f:
                        for row in csv.DictReader(f):
                            try:
                                event_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
                                days_away = (event_date - now_date).days
                                if days_away < 0 or days_away > 30:
                                    continue
                                etype = row.get("event_type", "")
                                if etype == "FOMC" and fomc_days is None:
                                    fomc_days = days_away
                                elif etype == "NFP" and nfp_days is None:
                                    nfp_days = days_away
                            except (ValueError, KeyError):
                                continue

                # Council latest
                council_row = conn.execute(
                    "SELECT consensus, confidence_weighted_score FROM council_sessions "
                    "ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
                council_consensus = council_row["consensus"] if council_row else "N/A"
                council_conf_raw = council_row["confidence_weighted_score"] if council_row else 0
                council_confidence = int(council_conf_raw * 100) if council_conf_raw and council_conf_raw <= 1 else int(council_conf_raw or 0)

                # Open positions
                open_paper = conn.execute(
                    "SELECT COUNT(*) FROM shadow_trades WHERE status='open' AND COALESCE(source,'paper')='paper'"
                ).fetchone()[0]
                open_live = conn.execute(
                    "SELECT COUNT(*) FROM shadow_trades WHERE status='open' AND source='live'"
                ).fetchone()[0]

            notify_premarket_brief(
                vix=vix, vix_change=vix_change, regime=regime,
                spy_futures_pct=0.0,  # Not available pre-market without live data feed
                ten_year=0.0,
                earnings_today=earnings_today,
                fomc_days=fomc_days, nfp_days=nfp_days,
                council_consensus=council_consensus,
                council_confidence=council_confidence,
                open_paper=open_paper, open_live=open_live,
            )
            print("[WATCH] Pre-market brief sent via Telegram.")
        except Exception as e:
            logger.warning("[WATCH] Pre-market brief failed: %s", e)

    def _send_eod_report(self):
        """4:00 PM ET — Send end-of-day P&L report."""
        import sqlite3
        from src.notifications.telegram import notify_eod_report, is_telegram_enabled
        if not is_telegram_enabled():
            return

        try:
            today_str = datetime.now(ET).strftime("%Y-%m-%d")
            with sqlite3.connect("ai_research_desk.sqlite3") as conn:
                conn.row_factory = sqlite3.Row

                # Paper open
                paper_open_row = conn.execute(
                    "SELECT COUNT(*) as cnt, COALESCE(SUM(pnl_dollars),0) as pnl "
                    "FROM shadow_trades WHERE status='open' AND COALESCE(source,'paper')='paper'"
                ).fetchone()

                # Paper closed today
                paper_closed_row = conn.execute(
                    "SELECT COUNT(*) as cnt, COALESCE(SUM(pnl_dollars),0) as pnl "
                    "FROM shadow_trades WHERE status='closed' AND COALESCE(source,'paper')='paper' "
                    "AND actual_exit_time LIKE ?", (f"{today_str}%",)
                ).fetchone()

                # Live open
                live_open_row = conn.execute(
                    "SELECT COUNT(*) as cnt, COALESCE(SUM(pnl_dollars),0) as pnl "
                    "FROM shadow_trades WHERE status='open' AND source='live'"
                ).fetchone()

                # Live closed today
                live_closed_row = conn.execute(
                    "SELECT COUNT(*) as cnt, COALESCE(SUM(pnl_dollars),0) as pnl "
                    "FROM shadow_trades WHERE status='closed' AND source='live' "
                    "AND actual_exit_time LIKE ?", (f"{today_str}%",)
                ).fetchone()

                # All-time win rate
                all_closed = conn.execute(
                    "SELECT COUNT(*) as total, "
                    "SUM(CASE WHEN pnl_dollars > 0 THEN 1 ELSE 0 END) as wins "
                    "FROM shadow_trades WHERE status='closed'"
                ).fetchone()
                wins = all_closed["wins"] or 0
                total = all_closed["total"] or 0
                losses = total - wins
                win_rate = wins / total if total > 0 else 0

                # Best/worst today
                best = conn.execute(
                    "SELECT ticker, pnl_pct FROM shadow_trades "
                    "WHERE status='closed' AND actual_exit_time LIKE ? "
                    "ORDER BY pnl_pct DESC LIMIT 1", (f"{today_str}%",)
                ).fetchone()
                worst = conn.execute(
                    "SELECT ticker, pnl_pct FROM shadow_trades "
                    "WHERE status='closed' AND actual_exit_time LIKE ? "
                    "ORDER BY pnl_pct ASC LIMIT 1", (f"{today_str}%",)
                ).fetchone()

                # VIX
                vix_row = conn.execute(
                    "SELECT vix FROM vix_term_structure ORDER BY collected_at DESC LIMIT 1"
                ).fetchone()
                vix = vix_row["vix"] if vix_row else 0.0
                vix_prev_row = conn.execute(
                    "SELECT vix FROM vix_term_structure ORDER BY collected_at DESC LIMIT 1 OFFSET 1"
                ).fetchone()
                vix_prev = vix_prev_row["vix"] if vix_prev_row else vix

                from src.features.regime import classify_regime
                regime = classify_regime({"vix_proxy": vix})

            notify_eod_report(
                paper_open=paper_open_row["cnt"], paper_open_pnl=paper_open_row["pnl"],
                paper_closed_today=paper_closed_row["cnt"], paper_closed_pnl=paper_closed_row["pnl"],
                live_open=live_open_row["cnt"], live_open_pnl=live_open_row["pnl"],
                live_closed_today=live_closed_row["cnt"], live_closed_pnl=live_closed_row["pnl"],
                win_rate=win_rate, wins=wins, losses=losses,
                best_ticker=best["ticker"] if best else "N/A",
                best_pct=best["pnl_pct"] if best else 0.0,
                worst_ticker=worst["ticker"] if worst else "N/A",
                worst_pct=worst["pnl_pct"] if worst else 0.0,
                regime=regime, vix=vix, vix_change=vix - vix_prev,
            )
            print("[WATCH] EOD report sent via Telegram.")
        except Exception as e:
            logger.warning("[WATCH] EOD report failed: %s", e)

    def _send_data_asset_report(self):
        """4:30 PM ET — Send data asset daily report."""
        import sqlite3
        from src.notifications.telegram import notify_data_asset_report, is_telegram_enabled
        if not is_telegram_enabled():
            return

        try:
            today_str = datetime.now(ET).strftime("%Y-%m-%d")
            with sqlite3.connect("ai_research_desk.sqlite3") as conn:
                training_total = conn.execute(
                    "SELECT COUNT(*) FROM training_examples"
                ).fetchone()[0]
                training_today = conn.execute(
                    "SELECT COUNT(*) FROM training_examples WHERE created_at LIKE ?",
                    (f"{today_str}%",),
                ).fetchone()[0]

                signal_total = conn.execute(
                    "SELECT COUNT(*) FROM setup_signals"
                ).fetchone()[0]
                signal_today = conn.execute(
                    "SELECT COUNT(*) FROM setup_signals WHERE created_at LIKE ?",
                    (f"{today_str}%",),
                ).fetchone()[0]

                backlog = conn.execute(
                    "SELECT COUNT(*) FROM training_examples WHERE quality_score IS NULL"
                ).fetchone()[0]

                quality_row = conn.execute(
                    "SELECT AVG(quality_score) FROM training_examples WHERE quality_score IS NOT NULL"
                ).fetchone()
                quality_avg = quality_row[0] if quality_row[0] else 0.0

                # Flywheel: examples from closed trades today
                flywheel = conn.execute(
                    "SELECT COUNT(*) FROM training_examples "
                    "WHERE source IN ('outcome_win','outcome_loss') AND created_at LIKE ?",
                    (f"{today_str}%",),
                ).fetchone()[0]

            notify_data_asset_report(
                training_total=training_total, training_today=training_today,
                training_target=2800,
                signal_zoo_total=signal_total, signal_zoo_today=signal_today,
                scoring_backlog=backlog, quality_avg=quality_avg,
                flywheel_count=flywheel,
            )
            print("[WATCH] Data asset report sent via Telegram.")
        except Exception as e:
            logger.warning("[WATCH] Data asset report failed: %s", e)

    def _check_vix_regime_alert(self):
        """Check VIX after each scan and alert on threshold crossings."""
        import sqlite3
        from src.notifications.telegram import notify_regime_alert, is_telegram_enabled
        if not is_telegram_enabled():
            return

        try:
            with sqlite3.connect("ai_research_desk.sqlite3") as conn:
                row = conn.execute(
                    "SELECT vix FROM vix_term_structure ORDER BY collected_at DESC LIMIT 1"
                ).fetchone()
                if not row:
                    return
                vix_now = row[0]

            thresholds = [20, 25, 30, 35, 40, 60]

            if self._last_vix_alert_level is None:
                self._last_vix_alert_level = vix_now
                return

            prev = self._last_vix_alert_level
            crossed = None

            for t in thresholds:
                if prev < t <= vix_now:  # Crossed upward
                    crossed = t
                elif prev > t >= vix_now:  # Crossed downward (use >= for boundary)
                    crossed = t
                elif prev >= t > vix_now:  # Crossed downward
                    crossed = t

            if crossed is not None:
                from src.features.regime import classify_regime
                regime_old = classify_regime({"vix_proxy": prev})
                regime_new = classify_regime({"vix_proxy": vix_now})

                # Qualification and sizing are regime-dependent heuristics
                qual_map = {"BULL_LOW_VOL": 30, "BULL_HIGH_VOL": 35, "TRANSITION": 40,
                            "CORRECTION": 65, "BEAR_EARLY": 70, "BEAR_ESTABLISHED": 80, "CRISIS": 90}
                sizing_map = {"BULL_LOW_VOL": 100, "BULL_HIGH_VOL": 80, "TRANSITION": 70,
                              "CORRECTION": 60, "BEAR_EARLY": 40, "BEAR_ESTABLISHED": 20, "CRISIS": 0}

                notify_regime_alert(
                    vix_now=vix_now, vix_prev=prev, threshold_crossed=crossed,
                    regime_old=regime_old, regime_new=regime_new,
                    qual_old=qual_map.get(regime_old, 40), qual_new=qual_map.get(regime_new, 40),
                    sizing_old=sizing_map.get(regime_old, 100), sizing_new=sizing_map.get(regime_new, 100),
                )
                self._last_vix_alert_level = vix_now
                print(f"[WATCH] VIX regime alert sent: crossed {crossed}")
            else:
                self._last_vix_alert_level = vix_now
        except Exception as e:
            logger.warning("[WATCH] VIX regime alert check failed: %s", e)

    def _send_weekly_digest(self):
        """Sunday 8 PM ET — Send full weekly digest."""
        import sqlite3
        from src.notifications.telegram import notify_weekly_digest, is_telegram_enabled
        if not is_telegram_enabled():
            return

        try:
            now = datetime.now(ET)
            period_end = now.strftime("%b %d")
            from datetime import timedelta
            week_ago = now - timedelta(days=7)
            period_start = week_ago.strftime("%b %d")
            week_ago_str = week_ago.strftime("%Y-%m-%d")

            with sqlite3.connect("ai_research_desk.sqlite3") as conn:
                conn.row_factory = sqlite3.Row

                # Trades this week
                opened_paper = conn.execute(
                    "SELECT COUNT(*) FROM shadow_trades WHERE COALESCE(source,'paper')='paper' "
                    "AND created_at >= ?", (week_ago_str,)
                ).fetchone()[0]
                opened_live = conn.execute(
                    "SELECT COUNT(*) FROM shadow_trades WHERE source='live' "
                    "AND created_at >= ?", (week_ago_str,)
                ).fetchone()[0]
                closed_paper = conn.execute(
                    "SELECT COUNT(*) FROM shadow_trades WHERE status='closed' AND COALESCE(source,'paper')='paper' "
                    "AND actual_exit_time >= ?", (week_ago_str,)
                ).fetchone()[0]
                closed_live = conn.execute(
                    "SELECT COUNT(*) FROM shadow_trades WHERE status='closed' AND source='live' "
                    "AND actual_exit_time >= ?", (week_ago_str,)
                ).fetchone()[0]

                # Win rate and expectancy (all time)
                wr_row = conn.execute(
                    "SELECT COUNT(*) as total, "
                    "SUM(CASE WHEN pnl_dollars > 0 THEN 1 ELSE 0 END) as wins, "
                    "AVG(pnl_dollars) as expectancy "
                    "FROM shadow_trades WHERE status='closed'"
                ).fetchone()
                win_rate = (wr_row["wins"] or 0) / max(wr_row["total"] or 1, 1)
                expectancy = wr_row["expectancy"] or 0

                # Best/worst this week
                best = conn.execute(
                    "SELECT ticker, pnl_pct FROM shadow_trades "
                    "WHERE status='closed' AND actual_exit_time >= ? "
                    "ORDER BY pnl_pct DESC LIMIT 1", (week_ago_str,)
                ).fetchone()
                worst = conn.execute(
                    "SELECT ticker, pnl_pct FROM shadow_trades "
                    "WHERE status='closed' AND actual_exit_time >= ? "
                    "ORDER BY pnl_pct ASC LIMIT 1", (week_ago_str,)
                ).fetchone()

                # P&L this week
                pnl_paper = conn.execute(
                    "SELECT COALESCE(SUM(pnl_dollars),0) FROM shadow_trades "
                    "WHERE status='closed' AND COALESCE(source,'paper')='paper' AND actual_exit_time >= ?",
                    (week_ago_str,)
                ).fetchone()[0]
                pnl_live = conn.execute(
                    "SELECT COALESCE(SUM(pnl_dollars),0) FROM shadow_trades "
                    "WHERE status='closed' AND source='live' AND actual_exit_time >= ?",
                    (week_ago_str,)
                ).fetchone()[0]

                # Data asset
                training_end = conn.execute("SELECT COUNT(*) FROM training_examples").fetchone()[0]
                training_start = training_end - conn.execute(
                    "SELECT COUNT(*) FROM training_examples WHERE created_at >= ?",
                    (week_ago_str,)
                ).fetchone()[0]
                signal_end = conn.execute("SELECT COUNT(*) FROM setup_signals").fetchone()[0]
                signal_start = signal_end - conn.execute(
                    "SELECT COUNT(*) FROM setup_signals WHERE created_at >= ?",
                    (week_ago_str,)
                ).fetchone()[0]
                backlog = conn.execute(
                    "SELECT COUNT(*) FROM training_examples WHERE quality_score IS NULL"
                ).fetchone()[0]
                quality_row = conn.execute(
                    "SELECT AVG(quality_score) FROM training_examples WHERE quality_score IS NOT NULL"
                ).fetchone()
                quality_avg = quality_row[0] if quality_row[0] else 0.0

                # VIX
                vix_row = conn.execute(
                    "SELECT vix FROM vix_term_structure ORDER BY collected_at DESC LIMIT 1"
                ).fetchone()
                vix = vix_row["vix"] if vix_row else 0.0
                vix_range = conn.execute(
                    "SELECT MIN(vix) as low, MAX(vix) as high FROM vix_term_structure "
                    "WHERE collected_at >= ?", (week_ago_str,)
                ).fetchone()

                from src.features.regime import classify_regime
                regime = classify_regime({"vix_proxy": vix})

                # Council
                council_sessions = conn.execute(
                    "SELECT COUNT(*) FROM council_sessions WHERE created_at >= ?",
                    (week_ago_str,)
                ).fetchone()[0]
                council_row = conn.execute(
                    "SELECT consensus, confidence_weighted_score FROM council_sessions "
                    "ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
                council_consensus = council_row["consensus"] if council_row else "N/A"
                council_conf = council_row["confidence_weighted_score"] if council_row else 0
                council_avg_conf = int(council_conf * 100) if council_conf and council_conf <= 1 else int(council_conf or 0)

            # Next week events
            import csv
            from pathlib import Path
            from datetime import timedelta as td
            next_week_start = now.date() + td(days=1)
            next_week_end = now.date() + td(days=7)
            events_next = []
            earnings_next = []

            cal_path = Path("data/reference/market_event_calendar.csv")
            if cal_path.exists():
                with open(cal_path, encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        try:
                            ed = datetime.strptime(row["date"], "%Y-%m-%d").date()
                            if next_week_start <= ed <= next_week_end:
                                events_next.append(f"{row.get('event_type','')} {row['date']}")
                        except (ValueError, KeyError):
                            continue

            notify_weekly_digest(
                period_start=period_start, period_end=period_end,
                opened_paper=opened_paper, opened_live=opened_live,
                closed_paper=closed_paper, closed_live=closed_live,
                win_rate=win_rate, expectancy=expectancy,
                best_ticker=best["ticker"] if best else "N/A",
                best_pct=best["pnl_pct"] if best else 0.0,
                worst_ticker=worst["ticker"] if worst else "N/A",
                worst_pct=worst["pnl_pct"] if worst else 0.0,
                pnl_paper=pnl_paper, pnl_live=pnl_live,
                training_start=training_start, training_end=training_end,
                signal_start=signal_start, signal_end=signal_end,
                scoring_backlog=backlog, quality_avg=quality_avg,
                canary_status="STABLE", llm_success_rate=0.78,
                regime=regime, vix=vix,
                vix_range_low=vix_range["low"] if vix_range and vix_range["low"] else vix,
                vix_range_high=vix_range["high"] if vix_range and vix_range["high"] else vix,
                spy_weekly_pct=0.0,
                council_sessions=council_sessions,
                council_consensus=council_consensus,
                council_avg_confidence=council_avg_conf,
                earnings_next_week=earnings_next, events_next_week=events_next,
            )
            print("[WATCH] Weekly digest sent via Telegram.")
        except Exception as e:
            logger.warning("[WATCH] Weekly digest failed: %s", e)

    def _check_earnings_proximity(self):
        """8:00 AM ET — Check open positions for upcoming earnings."""
        import sqlite3
        from src.notifications.telegram import notify_position_earnings_warning, is_telegram_enabled
        if not is_telegram_enabled():
            return

        try:
            with sqlite3.connect("ai_research_desk.sqlite3") as conn:
                conn.row_factory = sqlite3.Row

                open_trades = conn.execute(
                    "SELECT trade_id, ticker, actual_entry_price, pnl_dollars, pnl_pct "
                    "FROM shadow_trades WHERE status='open'"
                ).fetchall()

                if not open_trades:
                    return

                now_date = datetime.now(ET).date()
                for trade in open_trades:
                    ticker = trade["ticker"]
                    earnings = conn.execute(
                        "SELECT earnings_date, earnings_time FROM earnings_calendar "
                        "WHERE ticker = ? AND earnings_date >= ? "
                        "ORDER BY earnings_date ASC LIMIT 1",
                        (ticker, now_date.isoformat()),
                    ).fetchone()

                    if not earnings:
                        continue

                    try:
                        e_date = datetime.strptime(earnings["earnings_date"], "%Y-%m-%d").date()
                        days_until = (e_date - now_date).days
                    except (ValueError, TypeError):
                        continue

                    if 0 <= days_until <= 3:
                        notify_position_earnings_warning(
                            ticker=ticker,
                            days_until=days_until,
                            earnings_date=earnings["earnings_date"],
                            earnings_time=earnings["earnings_time"] or "TBD",
                            current_pnl=trade["pnl_dollars"] or 0,
                            current_pnl_pct=trade["pnl_pct"] or 0,
                        )
            print("[WATCH] Earnings proximity check complete.")
        except Exception as e:
            logger.warning("[WATCH] Earnings proximity check failed: %s", e)

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

    def _run_research_synthesis(self):
        """Sunday 6 PM ET — Run weekly research synthesis."""
        from src.data_collection.research_synthesizer import run_weekly_synthesis
        print("[WATCH] Running weekly research synthesis...")
        result = run_weekly_synthesis()
        papers_count = result.get("papers_reviewed", 0)
        actionable = result.get("actionable_count", 0)
        print(f"[WATCH] Research synthesis: {papers_count} papers reviewed, {actionable} actionable")

        # Send Telegram digest
        try:
            from src.notifications.telegram import send_telegram, is_telegram_enabled
            if is_telegram_enabled():
                digest = result.get("digest_summary", "No digest generated")
                send_telegram(
                    f"<b>WEEKLY RESEARCH DIGEST</b>\n\n"
                    f"Papers reviewed: {papers_count}\n"
                    f"Actionable: {actionable}\n\n"
                    f"{digest[:500]}"
                )
        except Exception:
            pass

    def _save_daily_metric_snapshot(self):
        """Save daily metric snapshot at EOD for MetricTrend chart."""
        import sqlite3
        db_path = "ai_research_desk.sqlite3"
        try:
            from src.training.versioning import save_metric_snapshot
            with sqlite3.connect(db_path) as conn:
                closed = conn.execute(
                    "SELECT pnl_pct, pnl_dollars FROM shadow_trades WHERE status = 'closed'"
                ).fetchall()
                pnls = [r[0] for r in closed if r[0] is not None]
                pnl_dollars = [r[1] for r in closed if r[1] is not None]
                open_count = conn.execute(
                    "SELECT COUNT(*) FROM shadow_trades WHERE status = 'open'"
                ).fetchone()[0]

            if not pnls:
                snapshot = {
                    "cumulative_pnl": 0, "win_rate": 0, "sharpe_ratio": 0,
                    "max_drawdown": 0, "expectancy": 0, "trade_count": 0,
                    "open_positions": open_count,
                }
            else:
                wins = [p for p in pnls if p > 0]
                mean_pnl = sum(pnls) / len(pnls)
                std_pnl = max((sum((p - mean_pnl) ** 2 for p in pnls) / len(pnls)) ** 0.5, 0.001)
                # Max drawdown from running P&L
                running = 0
                peak = 0
                max_dd = 0
                for p in pnl_dollars:
                    running += p
                    if running > peak:
                        peak = running
                    dd = peak - running
                    if dd > max_dd:
                        max_dd = dd

                snapshot = {
                    "cumulative_pnl": sum(pnl_dollars),
                    "win_rate": len(wins) / len(pnls),
                    "sharpe_ratio": mean_pnl / std_pnl if len(pnls) > 1 else 0,
                    "max_drawdown": max_dd,
                    "expectancy": sum(pnl_dollars) / len(pnl_dollars),
                    "trade_count": len(pnls),
                    "open_positions": open_count,
                }

            save_metric_snapshot(snapshot)
            logger.info(
                "[METRICS] Daily snapshot saved: %d trades, %.1f%% win rate",
                len(pnls), snapshot["win_rate"] * 100,
            )
        except Exception as e:
            logger.debug("[METRICS] Daily snapshot failed: %s", e)
