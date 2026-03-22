# AI Research Desk

A docs-first, local-first MVP for an always-on AI research desk that monitors the S&P 100, surfaces high-conviction short swing opportunities, sends institutional-style trade packets to Ryan's work email, and maintains a shadow paper-trading ledger for continuous learning.

## MVP objective

Answer one question:

**Can this system consistently surface useful, high-quality short swing ideas that improve decision quality without hurting day-job performance?**

## Version 1 at a glance

- Universe: S&P 100
- Primary mode: short swing equities
- Setup family: pullback in strong trend / relative strength continuation
- Expected hold period: typically 2 to 10 trading days
- Alert cadence:
  - Morning watchlist
  - Action packets only when threshold is cleared
  - End-of-day recap
- Quality philosophy: maximize idea quality even if there are zero packets for an entire week
- Event risk: earnings-adjacent trades are allowed, but must be specially labeled and sized more conservatively
- Position sizing: suggested framework based on $1,000 starting working capital
- Review loop: full post-trade review only on trades Ryan actually executes
- Execution: no autonomous live trading in MVP

## Repo contents

- `docs/charter/` - charter document
- `docs/blueprint/` - Version 1 blueprint
- `docs/packet_templates/` - trade packet structure and email format
- `docs/journal/` - journal schema and data dictionary
- `docs/milestones/` - milestone plan for MVP
- `docs/issues/` - initial issue backlog for GitHub
- `src/` - thin runnable skeleton
- `config/` - local configuration template

## Recommended stack

- Python
- Alpaca paper trading for shadow ledger and future API-first integration
- vectorbt for fast signal research
- LEAN as a later promotion gate for more rigorous validation
- Local SQLite for MVP journal storage
- SMTP email delivery from a dedicated assistant email to Ryan's work email

## Quick start

### 1. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Copy config template

```bash
cp config/settings.example.yaml config/settings.local.yaml
```

Fill in email credentials, Alpaca keys, and any future data provider settings.

### 3. Initialize the local journal database

```bash
python -m src.main init-db
```

### 4. Generate a demo packet

```bash
python -m src.main demo-packet
```

### 5. Run a placeholder scan

```bash
python -m src.main scan
```

## Suggested first implementation order

1. Finalize docs
2. Populate S&P 100 universe file
3. Stand up journal storage
4. Build packet generator
5. Add email sender
6. Add market data ingestion
7. Add feature engine and ranker
8. Add shadow paper ledger
9. Run 30-day bootcamp

## MVP success criteria

- 3 to 5 actionable packets per week on average when opportunity set is healthy
- Zero packets is acceptable in weak conditions
- Packets are concise, useful, and defensible
- Journal is complete for 100% of recommendations
- Shadow performance is measurable and reviewable
- Workflow does not materially disrupt work performance

## Notes

This repo is intentionally lightweight. The goal is to preserve focus, make progress quickly, and avoid overengineering before the core research loop proves it deserves expansion.
