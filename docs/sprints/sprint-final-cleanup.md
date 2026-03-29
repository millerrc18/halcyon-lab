# Sprint: Final Cleanup & Verification — Close Every Gap
# PRIORITY: Ryan needs to go to bed. Fix everything, verify everything.

> **This is a cleanup sprint, not a feature sprint.**
> Only acceptable changes: fix bugs, update docs, add missing config, verify wiring.
> NO new features. NO refactoring.
>
> **Pre-read:**
> ```
> cat AGENTS.md
> cat CHANGELOG.md
> cat src/council/agents.py
> cat src/council/protocol.py
> cat src/council/engine.py
> cat src/council/value_tracker.py
> cat src/scheduler/watch.py
> cat src/notifications/telegram.py
> cat src/main.py
> cat config/settings.example.yaml
> cat docs/architecture.md
> cat docs/roadmap.md
> ```
>
> **Run before starting:** `python -m pytest tests/ -x -q`

---

# ══════════════════════════════════════════════════════════════
# PART 1: DOCUMENTATION (must match code reality)
# ══════════════════════════════════════════════════════════════

## 1.1 Update AGENTS.md counts

Run these commands and put EXACT numbers on line 1:
```bash
echo "Python files:" && find src -name "*.py" ! -path "*__pycache__*" ! -name "*backup*" | wc -l
echo "Test files:" && find tests -name "*.py" | wc -l
echo "Tests:" && find tests -name "*.py" -exec grep -c "def test_" {} + 2>/dev/null | awk -F: '{s+=$2}END{print s}'
echo "CLI commands:" && grep -c "add_parser" src/main.py
echo "DB tables:" && python3 -c "
import sqlite3; conn = sqlite3.connect('ai_research_desk.sqlite3')
from src.journal.store import initialize_database; initialize_database()
from src.council.engine import init_council_tables; init_council_tables()
tables = conn.execute(\"SELECT COUNT(*) FROM sqlite_master WHERE type='table'\").fetchone()[0]
print(tables)
" 2>/dev/null || echo "Run on live system"
echo "Notifications:" && grep -c "^def notify_" src/notifications/telegram.py
echo "Research docs:" && ls docs/research/*.md | wc -l
```

## 1.2 Update docs/architecture.md

This file is stale (last updated March 27, pre-both-sprints). Add sections for:

**New modules (add to module inventory):**
- `src/features/traffic_light.py` — Traffic Light regime overlay (VIX 20/30 + 200-DMA 3% + credit spread 0.5σ/1.5σ → sizing multiplier)
- `src/data_enrichment/earnings_signals.py` — PEAD enrichment (5 signals: proximity, surprise, concordance, revision velocity, recommendation inconsistency)
- `src/evaluation/hshs_live.py` — Live HSHS computation from database state (5 dimensions)
- `src/evaluation/system_validator.py` — System validation (50+ checks, 8 categories)
- `src/council/agents.py` — REWRITTEN: 5 analytical-lens agents (tactical_operator, strategic_architect, red_team, innovation_engine, macro_navigator)
- `src/council/protocol.py` — REWRITTEN: Vote-first Modified Delphi, conditional Round 2, rate limiters
- `src/council/engine.py` — REWRITTEN: 1-2 round flow, result_json storage, calibration, value tracking
- `src/council/value_tracker.py` — NEW: Counterfactual P&L computation, per-agent tracking

**Deleted modules:**
- `src/scheduler/overnight.py` — consolidated into watch.py
- `src/shadow_trading/broker.py` — unused abstraction

**New database tables:**
- `traffic_light_state` — regime persistence tracking
- `council_calibrations` — falsifiable prediction tracking
- `council_debug_log` — full prompt/response replay
- `council_parameter_log` — parameter change attribution
- `council_parameter_state` — current active parameters
- `user_notes` — dashboard notes (schema ready, page pending)
- `validation_results` — system validator output

**New columns:**
- `shadow_trades.signal_price` — captured at scan time for IS tracking
- `shadow_trades.implementation_shortfall_bps` — computed on fill
- `council_sessions.result_json` — full structured session output
- `council_votes.direction` — new schema (bullish/neutral/bearish)
- `council_votes.confidence_float` — 0.0-1.0 scale
- `council_votes.assessment_json` — complete agent assessment blob

**New API endpoints:**
- `GET /api/health/hshs` — live HSHS score
- `GET /api/system/validation` — system validator results

**Data flow changes:**
- Scan pipeline: now computes Traffic Light ONCE per scan, injects into all tickers
- Enrichment: now includes PEAD earnings signals per ticker (conditional on proximity ≤30 days)
- Governor: now accepts traffic_light_multiplier parameter, applies before all other checks
- Executor: now captures signal_price and computes IS on fill
- Council: vote-first protocol, 1-2 rounds, parameter auto-application with rate limiters

## 1.3 Update docs/roadmap.md

Add confirmed decisions:
- Strategy #1: Pullback (LIVE)
- Strategy #2: Mean Reversion (Phase 2, Connors RSI(2), ρ = −0.35)
- Strategy #3: Evolved PEAD (Phase 3, composite earnings info system)
- RL: Dr. GRPO (loss_type="dr_grpo" in TRL GRPOTrainer), skip DPO
- Breakout = pullback feature, not separate strategy
- Traffic Light: built and deployed ✓
- Council v2: built and deployed ✓
- IS tracking: built and deployed ✓
- PEAD enrichment: built and deployed ✓
- HSHS live: built and deployed ✓

---

# ══════════════════════════════════════════════════════════════
# PART 2: LOGGING & OBSERVABILITY
# ══════════════════════════════════════════════════════════════

## 2.1 Configure file logging in watch.py

Find where logging is configured in watch.py (may be in `__init__` or at module level).
Add a RotatingFileHandler so logs persist to disk:

```python
import logging
from logging.handlers import RotatingFileHandler

# Add at the start of the WatchDog.__init__ or the module-level setup:
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

file_handler = RotatingFileHandler(
    log_dir / "halcyon.log",
    maxBytes=10 * 1024 * 1024,  # 10 MB per file
    backupCount=7,               # Keep 7 rotated files (7 days at ~10MB/day)
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))

# Add to root logger so ALL modules write to the file
logging.getLogger().addHandler(file_handler)
```

Also ensure the root logger level is INFO (not WARNING):
```python
logging.getLogger().setLevel(logging.INFO)
```

Add `logs/` to `.gitignore` if not already there.

## 2.2 Verify terminal output for key operations

Run a dry scan and verify you see:
```bash
python -m src.main scan --dry-run --verbose 2>&1 | head -50
```

Verify output includes lines for:
- Universe loaded
- Features computed
- Enrichment (fundamentals, insiders, news, macro, earnings)
- Traffic Light (score, multiplier, regime)
- Ranking
- Packet-worthy candidates

Run a council session and verify output:
```bash
python -m src.main council 2>&1 | head -30
```

Verify output includes:
- "Running AI Council session"
- Agent assessments with direction and confidence
- Consensus result
- Cost

---

# ══════════════════════════════════════════════════════════════
# PART 3: CONFIG UPDATES
# ══════════════════════════════════════════════════════════════

## 3.1 Add execution config to settings.example.yaml

Find the `shadow_trading:` section in `config/settings.example.yaml`. After it, add:

```yaml
# ── Execution Configuration ─────────────────────────────────
execution:
  order_type: "market"           # "market" or "limit_at_ask"
  limit_timeout_seconds: 300     # Cancel unfilled limits after 5 minutes
```

---

# ══════════════════════════════════════════════════════════════
# PART 4: COUNCIL V2 VERIFICATION
# ══════════════════════════════════════════════════════════════

## 4.1 Verify import chain

```python
# This must succeed without error:
from src.council.agents import AGENT_NAMES, AGENT_PROMPTS, AGENT_DATA_FUNCTIONS
from src.council.protocol import aggregate_votes, tally_votes, apply_rate_limiters, PARAMETER_DEFAULTS
from src.council.engine import CouncilEngine, init_council_tables
from src.council.value_tracker import compute_attribution, get_rolling_value_summary

print(f"Agents: {AGENT_NAMES}")
print(f"Data functions: {list(AGENT_DATA_FUNCTIONS.keys())}")
print(f"Defaults: {PARAMETER_DEFAULTS}")
print("All council imports OK ✓")
```

## 4.2 Verify database tables created

```python
from src.council.engine import init_council_tables
from src.council.value_tracker import init_value_tables

init_council_tables()
init_value_tables()

import sqlite3
conn = sqlite3.connect("ai_research_desk.sqlite3")
tables = [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'council%'"
).fetchall()]
print(f"Council tables: {tables}")

# Must include: council_sessions, council_votes, council_calibrations, council_debug_log
# Must include: council_parameter_log, council_parameter_state

# Verify new columns
cols = [r[1] for r in conn.execute("PRAGMA table_info(council_votes)").fetchall()]
assert "direction" in cols, "MISSING: council_votes.direction"
assert "confidence_float" in cols, "MISSING: council_votes.confidence_float"
assert "assessment_json" in cols, "MISSING: council_votes.assessment_json"

cols = [r[1] for r in conn.execute("PRAGMA table_info(council_sessions)").fetchall()]
assert "result_json" in cols, "MISSING: council_sessions.result_json"

print("All council tables and columns verified ✓")
```

## 4.3 Fix council tests

The old council tests reference deleted agent names (risk_officer, alpha_strategist, etc.).
Update `tests/test_council*.py` to use new agent names:

- `risk_officer` → `red_team`
- `alpha_strategist` → `tactical_operator`
- `data_scientist` → `innovation_engine`
- `regime_analyst` → `macro_navigator`
- `devils_advocate` → (removed, no replacement — update tests to use 5 agents)

Also update any tests that expect:
- `position` field → now `direction` (bullish/neutral/bearish)
- `confidence` as 1-10 integer → now `confidence` as 0.0-1.0 float
- `vote` as reduce/hold/increase → now mapped via backward compat
- 3 rounds always → now 1-2 rounds (conditional)

Run tests after fixing:
```bash
python -m pytest tests/test_council*.py -v
```

## 4.4 Verify no references to old agent names in active code

```bash
grep -rn "risk_officer\|alpha_strategist\|data_scientist\|regime_analyst\|devils_advocate" \
    src/ --include="*.py" | grep -v backup | grep -v __pycache__ | grep -v "v1_backup"
```

**Must return ZERO results.** If any found, fix them.

---

# ══════════════════════════════════════════════════════════════
# PART 5: DATA COLLECTION VERIFICATION
# ══════════════════════════════════════════════════════════════

## 5.1 Verify all overnight collectors

```python
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect("ai_research_desk.sqlite3")
cutoff = (datetime.utcnow() - timedelta(days=3)).isoformat()

collectors = [
    ("macro_snapshots", "date"),
    ("insider_transactions", "created_at"),
    ("edgar_filings", "created_at"),
    ("short_interest", "created_at"),
    ("options_chains", "created_at"),
    ("vix_term_structure", "date"),
    ("earnings_calendar", "created_at"),
    ("sector_rotation", "created_at"),
    ("economic_calendar", "created_at"),
    ("analyst_estimates", "created_at"),
]

for table, col in collectors:
    try:
        total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        recent = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} > ?", (cutoff,)).fetchone()[0]
        status = "✓" if total > 0 else "⚠️ EMPTY"
        print(f"  {table}: {total} total, {recent} recent {status}")
    except Exception as e:
        print(f"  {table}: ❌ {e}")
```

## 5.2 Verify all API endpoints

```bash
echo "API endpoints in cloud_app.py:"
grep -c "@app.get\|@app.post\|@app.put\|@app.delete" src/api/cloud_app.py
echo ""
echo "Council-specific endpoints:"
grep "@app.*council\|@app.*hshs\|@app.*validation\|@app.*health" src/api/cloud_app.py
```

---

# ══════════════════════════════════════════════════════════════
# PART 6: FINAL VERIFICATION
# ══════════════════════════════════════════════════════════════

## 6.1 All tests pass

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tee /tmp/final_test.log
echo ""
tail -10 /tmp/final_test.log
```

**ZERO failures.**

## 6.2 Frontend builds

```bash
cd frontend && npm run build 2>&1 | tail -5 && cd ..
```

## 6.3 No orphaned imports

```bash
echo "Imports of deleted modules:"
grep -rn "from src.scheduler.overnight\|from src.shadow_trading.broker" src/ tests/ --include="*.py" | grep -v __pycache__
echo "(must be empty)"

echo ""
echo "Imports of old council v2 files:"
grep -rn "protocol_v2\|agents_v2\|engine_v2" src/ --include="*.py" | grep -v backup | grep -v __pycache__
echo "(must be empty)"
```

## 6.4 Commit and push

```bash
git add -A
git status
git commit -m "cleanup: final verification — docs, logging, config, council tests, data verification

- AGENTS.md counts verified and corrected
- docs/architecture.md updated with all new modules, tables, columns, endpoints
- docs/roadmap.md updated with confirmed strategy decisions
- File logging with rotation added to watch.py (logs/halcyon.log, 10MB × 7)
- config/settings.example.yaml: execution config added
- Council tests updated for v2 agent names and schema
- Zero old agent references in active code
- All data collection tables verified
- All tests pass, frontend builds"

git push origin main
```

---

# Sprint Documentation Checklist

### Tier 1 (MANDATORY):
- [ ] AGENTS.md counts match code
- [ ] docs/architecture.md updated
- [ ] docs/roadmap.md updated
- [ ] Council tests pass
- [ ] Zero orphaned imports
- [ ] All tests pass
- [ ] Frontend builds
- [ ] File logging configured
