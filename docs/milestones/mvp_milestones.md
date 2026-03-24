# MVP Milestones

## Milestone 1 - Foundation
- Create repo and docs
- Lock blueprint and packet template
- Stand up local config and SQLite journal
- Create thin runnable CLI skeleton

## Milestone 2 - Research Core
- Populate S&P 100 universe
- Add market data ingestion layer
- Add first-pass feature engine
- Add basic ranking logic for pullback-in-trend setup

## Milestone 3 - Communication Layer
- Build packet formatter
- Build morning watchlist email
- Build action packet email
- Build end-of-day recap email

## Milestone 4 - Shadow Ledger
- Connect Alpaca paper account or equivalent shadow-execution adapter
- Log entry / exit events
- Track outcome metrics
- Separate earnings-adjacent trades as distinct class

## Milestone 5 - Review Loop
- Add assistant postmortem generation
- Add Ryan review flow for taken trades
- Add scorecard output for 30-day bootcamp

## Milestone 6 - Bootcamp (30-day intensive calibration)
- Operates in aggressive paper-trading mode — no position limits, loose thresholds, maximum data collection
- Phase 1 (Days 1–10): High-volume data collection, early threshold tuning
- Phase 2 (Days 11–20): Statistical optimization of scoring weights and cutoffs based on Phase 1 outcomes
- Phase 3 (Days 21–30): ML/LLM learning — train or fine-tune ranking models on accumulated outcome data
- Email mode configurable: silent / daily summary / full stream (toggled by Ryan at any time)
- Exit evaluation: shadow performance metrics, optimization lift, ML vs deterministic comparison, promotion readiness
