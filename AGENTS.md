# AGENTS.md

## Purpose

This file is the core operating document for any LLM, coding agent, or autonomous assistant working inside this repository.

The repository exists to build an **AI Research Desk** for Ryan: a focused, always-on assistant that monitors the S&P 100, surfaces high-conviction short swing opportunities, generates institutional-style trade packets, emails those packets to Ryan's work email, and maintains a shadow paper-trading ledger for learning and evaluation.

This repo is **not** a generic trading bot repo. It is a docs-first, quality-first, risk-aware research system.

## North-star question

Everything in this repository should help answer this question:

**Can this system consistently surface useful, high-quality short swing ideas that improve decision quality without hurting day-job performance?**

If a change does not clearly help answer that question, it is probably out of scope for the MVP.

## MVP scope

### In scope
- S&P 100 universe only
- Short swing equities only
- Primary setup family: pullback in strong trend / relative strength continuation
- Flexible hold period, usually 2 to 10 trading days
- Morning watchlist
- Action packets only when a high threshold is cleared
- End-of-day recap
- Shadow paper trading
- Local-first runtime
- Journal-driven learning
- Suggested position-sizing framework based on $1,000 starting capital
- Earnings-adjacent trades allowed, but only with special labeling and more conservative sizing

### Out of scope
- Autonomous live order placement
- Intraday-first mode as the default behavior
- Options or derivatives
- Margin-dependent strategies
- Multi-asset expansion
- Heavy dashboard/UI work before the core loop is validated
- Fine-tuning the LLM before bootcamp phase (authorized during M6 bootcamp — see Bootcamp specification)
- Feature creep that increases noise or operational burden

## Product philosophy

### 1. Quality over quantity
The assistant should prefer sending no packet for a week over sending weak ideas. It must never force trade ideas to satisfy activity goals.

### 2. Research first, execution later
The MVP is a research desk with shadow execution, not an autonomous trader.

### 3. Selective over noisy
The assistant should be calm, sparse, and high-signal. It should interrupt only when there is a genuinely packet-worthy setup.

### 4. Workday compatibility matters
The system must fit around a 9-to-5 schedule. Avoid designs that assume constant manual supervision.

### 5. Every recommendation is data
All recommendations should be logged whether Ryan acts on them or not.

### 6. Modular growth
Build components so the system can later expand into intraday mode, stricter backtesting, broader automation, or richer learning without a full rewrite.

## Intended operating model

The assistant is an **AI research analyst**.

Its responsibilities:
- Scan the S&P 100 on a schedule
- Rank names by opportunity quality
- Generate concise but defensible trade packets
- Send a morning watchlist, action packets, and an end-of-day recap
- Maintain a shadow paper ledger
- Track open theses until exit, invalidation, or timeout
- Learn from outcomes and post-trade reviews

Ryan's responsibilities:
- Review packets
- Decide whether to act
- Execute manually if desired
- Complete full post-trade review only on trades he actually takes

## Core constraints

### Universe
- S&P 100 only
- Favor highly liquid names
- Avoid thin names and low-quality execution conditions

### Setup family
The default setup family is:

**Pullback in strong trend / relative strength continuation**

Interpretation:
- The stock is already strong relative to the market
- The medium-term trend is constructive
- The stock pulls back into a zone where reward/risk improves
- The continuation thesis is easy to explain and invalidate

### Event risk
Earnings-adjacent trades are allowed, but they must be treated as a distinct risk class.

Any packet with earnings exposure must include:
- Next earnings date
- Whether the expected hold window overlaps earnings
- Elevated gap-risk warning
- Whether the thesis assumes exit before earnings or continued hold
- More conservative sizing guidance

All earnings-adjacent trades should be tagged separately in the journal.

### Position sizing
Default MVP framework:
- Starting capital assumption: $1,000
- Planned risk per trade: 0.5% to 1.0% of capital
- Approximate planned loss: $5 to $10 per trade
- Max simultaneous positions: 2

Packets should include:
- Suggested dollar allocation
- Percent of capital
- Estimated dollar risk to stop
- Warning if the setup is awkward or impractical at the current account size

## Communication standard

### Email cadence
- Morning watchlist
- Action packets only for true high-conviction setups
- End-of-day recap

### Packet style
Default tone:
- Crisp analyst
- Executive brevity
- Structured output

The assistant should also be able to answer follow-up questions and defend its reasoning in more detail when asked.

### Packet structure
Each packet should contain:
- Ticker and company name
- Setup type
- Why now
- Entry zone
- Stop / invalidation
- Target(s)
- Expected hold period
- Position sizing guidance
- Risks and reasons to pass
- Monitoring plan

The top of the packet should be a quick bullet brief. The lower section can contain deeper supporting analysis.

## Technical direction

### Core stack
- Python
- Alpaca paper trading for shadow execution and future API-first expansion
- vectorbt for fast strategy and signal testing
- LEAN as a later promotion gate for more rigorous backtesting
- SQLite for MVP journal storage
- SMTP email delivery from a dedicated assistant email to Ryan's work email

### Current architecture preference
- Docs first
- Thin runnable skeleton
- Local-first runtime
- Cloud backup optional later

## Repository priorities

When deciding what to build next, prefer work in this order:

1. Clarify docs and scope
2. Make the journal reliable
3. Make packet generation clean and standardized
4. Make scanning and ranking useful
5. Make email delivery reliable
6. Make shadow paper logging measurable
7. Improve evaluation and learning loops
8. Expand only after MVP gates are met

## Definition of success for MVP

### Process success
- Morning watchlist delivered reliably
- Roughly 3 to 5 actionable packets per week when opportunity set is healthy
- Zero packets is acceptable in weak conditions
- Journal is complete for 100% of recommendations
- Workflow remains helpful and non-disruptive during the workday

### Performance success
- Shadow paper performance is measurable
- Recommendation quality is visibly high
- False positives are limited
- Reasoning is concise and defensible
- Earnings-adjacent trades can be evaluated separately from normal trades

## Promotion gates

Do not expand scope unless the system clears these gates:

1. Recommendation quality is consistently high
2. Shadow performance is acceptable
3. Workflow fits Ryan's real life and workday
4. Journal quality is mature enough to support stronger learning and ranking

Only after these gates should the project consider:
- Live approval-gated execution support
- Intraday expansion
- Broader universes
- Fine-tuning or additional model layers

## Bootcamp specification (Milestone 6)

The 30-day bootcamp is an intensive calibration phase, not a passive observation period. The system should trade aggressively on paper to maximize data collection and learning.

### Bootcamp operating mode
- **No position limits** — the system may hold as many simultaneous shadow positions as it wants
- **Loose qualification thresholds** — lower the bar to generate high trade volume for statistical learning
- **All trades are shadow/paper only** — no live execution during bootcamp under any circumstances
- **Every trade is logged** — full journal entry for every recommendation, entry, exit, and outcome

### Three-phase learning arc

**Phase 1 — Data collection (Days 1–10):**
- Run with loose filters and high volume
- Prioritize breadth of data over precision
- Begin threshold tuning based on early outcome patterns
- Goal: accumulate a large, diverse dataset of trade outcomes

**Phase 2 — Statistical optimization (Days 11–20):**
- Analyze Phase 1 results
- Auto-propose adjusted scoring weights and qualification cutoffs based on measured outcomes
- Test revised rules against the Phase 1 dataset
- Goal: find scoring parameters that would have filtered for the best outcomes

**Phase 3 — ML/LLM learning (Days 21–30):**
- Use accumulated outcome data to train or fine-tune ranking models
- Compare learned model performance against deterministic rules
- Evaluate whether learned weights meaningfully outperform the rule-based ranker
- Goal: decide whether to promote learned ranking to production or stay with tuned deterministic rules

### Bootcamp email modes (configurable)
Ryan can toggle between these modes at any time during bootcamp:
- **Silent** — log everything, no emails sent, review after
- **Daily summary** — one email per day summarizing all activity
- **Full stream** — send every packet in real time

### Bootcamp exit criteria
At the end of 30 days, evaluate:
1. Shadow performance metrics (expectancy, win rate, avg gain vs avg loss, max drawdown)
2. Whether statistical optimization improved outcomes vs Phase 1 baseline
3. Whether ML/LLM ranking outperformed tuned deterministic rules
4. Overall trade quality and false positive rate
5. Whether the system is ready for promotion to approval-gated live execution

## Guidance for future LLM agents

### When making product or engineering decisions
Prefer:
- simpler architectures
- explicit schemas
- deterministic logging
- narrow, testable features
- readable docs
- conservative assumptions

Avoid:
- overengineering
- feature sprawl
- vague abstractions
- hidden state
- noisy alerting
- autonomous behaviors that bypass current risk boundaries

### When editing docs
Keep language:
- direct
- structured
- professional
- concise
- practical

### When writing code
- Favor clarity over cleverness
- Keep modules small and composable
- Add docstrings where behavior is not obvious
- Make it easy to test individual components
- Avoid hard-coding secrets or credentials
- Preserve local-first operability

### When uncertain
Use the repo's north-star question and MVP scope as the tie-breaker.

If a choice would make the system noisier, more complex, or less aligned with Ryan's workday constraints, do not make that choice unless the repo docs are explicitly updated to authorize it.

## Canonical docs

Use these files as primary references:
- `README.md`
- `docs/blueprint/version1_blueprint.md`
- `docs/packet_templates/trade_packet_v1.md`
- `docs/journal/journal_schema_v1.md`
- `docs/milestones/mvp_milestones.md`
- `docs/issues/initial_issue_backlog.md`
- `docs/charter/AI_Research_Desk_Project_Charter.docx`

If there is a conflict, prefer:
1. Charter intent
2. Blueprint scope
3. This AGENTS.md operating guidance
4. Implementation details in code
