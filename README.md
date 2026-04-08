# Prediction Tracker

AI-powered analysis and verification of predictions made by Ukrainian public figures.

## What it does

- Collects public statements from Telegram channels and news sites
- Extracts specific predictions using LLM
- Verifies predictions against real events with confidence scoring
- Provides interactive Telegram bot for querying results (RAG)

## Tech Stack

- Python 3.11+, FastAPI, SQLAlchemy 2.0
- PostgreSQL + pgvector (vector search)
- LiteLLM (provider-agnostic LLM abstraction)
- Docker, AWS (EC2 + RDS)

## Status

Under development

## License

MIT
