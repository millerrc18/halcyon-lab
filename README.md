# Halcyon Lab

An autonomous AI trading desk that scans the S&P 100, generates institutional-quality trade commentary using a fine-tuned LLM, executes bracket orders via Alpaca paper trading, and continuously improves through a self-training pipeline with quality gates.

## Features

- **Systematic Scoring**: 0-100 composite score from 20+ technical indicators
- **7+ Data Sources**: Technical, regime, sector, fundamentals, insiders, news, macro
- **LLM Commentary**: Ollama/Qwen3-8B generates analyst-style trade packets
- **Bracket Orders**: Automated entry + stop + target via Alpaca paper trading
- **Risk Governor**: 7 safety checks + kill switch to halt all trading
- **Training Pipeline**: Three-stage curriculum SFT + DPO with quality gates
- **Walk-Forward Backtesting**: Validate model performance on historical data
- **A/B Model Evaluation**: Shadow evaluation before model promotion
- **Dashboard**: React web interface with WebSocket live updates
- **Auditor Agent**: Daily and weekly automated system health checks
- **CTO Report**: Comprehensive performance analytics

## Prerequisites

- Python 3.12+
- Node.js 18+ (for dashboard)
- Ollama (for local LLM inference)
- Alpaca paper trading account
- API keys: Finnhub (free), FRED (free), Anthropic (for training data generation)

## Quick Start

```bash
# 1. Clone and setup
git clone <repo-url> && cd halcyon-lab
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# 2. Configure
cp config/settings.example.yaml config/settings.local.yaml
# Edit config/settings.local.yaml with your API keys

# 3. Initialize
python -m src.main init-db
python -m src.main preflight

# 4. Pull LLM model
ollama pull qwen3:8b

# 5. Run a scan
python -m src.main scan --verbose --dry-run

# 6. Start the dashboard
cd frontend && npm install && npm run build && cd ..
python -m src.main dashboard

# 7. Start the automated watch loop
python -m src.main watch
```

## Training Data Generation

```bash
# Historical backfill (generates training examples from real outcomes)
python -m src.main backfill-training --months 12 --yes

# Classify difficulty and curriculum stage
python -m src.main classify-training-data

# Score quality with LLM-as-judge
python -m src.main score-training-data

# Validate dataset health
python -m src.main validate-training-data

# Fine-tune
python -m src.main train --force
```

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full system architecture, database schema, and data flow diagrams.

## Documentation

- [Architecture](docs/architecture.md) — System design, database schema, API routes
- [Training Guide](docs/training-guide.md) — Training data pipeline, quality scoring, curriculum
- [Roadmap](docs/roadmap.md) — 5-phase development plan with performance gates
- [Email Setup](docs/guides/email_setup.md) — SMTP configuration guide

## License

MIT
