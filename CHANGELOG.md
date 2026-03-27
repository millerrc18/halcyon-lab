# Changelog

## 2026-03-27 — Live Trade Reconciliation

### New Features
- **`reconcile-live` CLI Command** — Detects orphaned Alpaca positions (on broker but not in DB) and stale DB records (in DB but not on broker); backfills or marks closed with `--dry-run` option
- **Live Ledger Reconcile Button** — Disabled button with tooltip showing CLI command for local execution

### Fixes
- **Fractional Shares** — `get_live_positions()`, `get_all_positions()`, `get_position()` in alpaca_adapter now use `float(qty)` instead of `int(qty)` to support fractional share positions

### Backend
- New `POST /api/live/reconcile` endpoint (returns cloud_mode error — local CLI only)
- New `src/shadow_trading/reconcile.py` module with `reconcile_live_trades()` function

### Tests
- 5 new tests: dry-run safety, orphan backfill, stale marking, no-discrepancy, paper-trade isolation

---

## 2026-03-27 — Dashboard Polish Sprint

### New Features
- **Research Docs on Cloud** — 35+ markdown docs served via `research_docs` Postgres table with category sidebar and search
- **Council Session Detail View** — Expandable session rows with full agent vote cards, vote distribution chart, dissent highlighting
- **Activity Feed Cloud Polling** — Polling fallback for cloud mode (60s) with event-type icons
- **Live Trade Ledger** — New page for $100 Alpaca live account with equity curve, open/closed tables, header metrics
- **Shadow Ledger Enhancements** — Metrics strip (equity, PF, DD), expandable trade detail rows, 4 viz tabs (equity curve, distribution, sector heatmap, calendar)
- **Hardware Roadmap** — Phase 2 and Phase 4 build specs with costs and unlock descriptions
- **Monthly Cost Timeline** — Visual bar chart of per-phase monthly costs

### Fixes
- **Audit Banner** — Parses raw JSON/code fences from audit summary, shows clean text
- **Shadow Equity** — Uses `shadow/account` endpoint (starting_capital + closed_pnl) instead of potentially wrong `alpaca_equity`
- **KPI Thresholds** — Sharpe/Win Rate show with >= 2 trades (was >= 5)
- **Confidence Calibration** — Shows "< X/50 trades" instead of "--"
- **Rubric Score** — Shows "Not scored yet" with tooltip instead of "n/a"
- **Health Score Dimensions** — All 5 dimensions (Performance, Model Quality, Data Asset, Flywheel, Defensibility) now computed from real data with metric breakdowns
- **Review Tab Removed** — Replaced with Live Ledger in sidebar navigation

### Backend
- 8 new cloud API endpoints: `/api/council/session/{id}`, `/api/activity/feed`, `/api/live/trades`, `/api/live/summary`, `/api/settings` (GET/POST), updated `/api/docs`, `/api/health/score`
- `research_docs` table added to sync pipeline
- Research synthesis wired to Sunday 6 PM schedule
- Daily metric snapshots at 4 PM EOD (not just Saturday)
- Nightly Telegram notification for new research papers

### Components
- New `Tooltip.jsx` — Hover tooltip with 300ms delay
- New `LiveLedger.jsx` — Full live trading ledger page
- Updated `ActivityFeed.jsx` — Cloud polling fallback + event icons
- Updated `Council.jsx` — Expandable session rows
- Updated `ShadowLedger.jsx` — Enhanced with viz tabs + trade expansion

### Roadmap
- Updated to 6 phases (added Phase 6 — Multi-Desk Expansion)
- Phase costs updated: $64 → $125 → $155 → $220 → $500+
- Hardware roadmap section added
