# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`prophet-checker` — AI-powered analysis and verification of predictions made by Ukrainian public figures. Pipeline: **collect** public statements (Telegram channels, news) → **extract** specific predictions with an LLM → **verify** them against real events with confidence scoring → serve answers via a RAG Telegram bot. The installed package is `prophet_checker`; the repo/product name is "prediction-tracker".

Current state: pre-deployment. The ingestion pipeline and the FastAPI HTTP trigger (`POST /ingest/run`) work end-to-end. The verifier is the most actively-iterated area. The Telegram bot and RAG query endpoint are designed but not yet built.

## Commands

All commands use the project venv at `.venv` (Python 3.14). Source lives under `src/`, installed editable.

```bash
# Setup
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
cp .env.example .env                       # then fill in API keys / Telegram creds

# Database (Postgres + pgvector via Docker)
docker compose up -d                       # container: prophet_postgres
.venv/bin/alembic upgrade head             # apply migrations
docker compose down -v && docker compose up -d && .venv/bin/alembic upgrade head   # full reset (drops volume)

# Run the API (uvicorn on 127.0.0.1:8000)
.venv/bin/python -m prophet_checker
curl localhost:8000/health
curl -X POST localhost:8000/ingest/run     # trigger one ingestion cycle

# Tests (unit + integration use in-memory fakes — no Docker / network needed)
.venv/bin/python -m pytest tests/ -q                                                            # full suite
.venv/bin/python -m pytest tests/test_ingestion_orchestrator.py -v                              # one file
.venv/bin/python -m pytest tests/test_ingestion_orchestrator.py::test_run_cycle_no_active_sources -v   # one test
.venv/bin/python -m pytest tests/ --cov=prophet_checker --cov-report=term-missing               # coverage

# Lint / format (ruff; line length 100)
.venv/bin/ruff check .
.venv/bin/ruff format .

# New migration after changing models/db.py
.venv/bin/alembic revision --autogenerate -m "description"

# Integration smoke — hits REAL Postgres + Telegram + LLM APIs (~$0.001–0.005/run)
.venv/bin/python scripts/ingestion/integration_smoke.py --channel @arestovich --limit 1
.venv/bin/python scripts/ingestion/integration_smoke.py --channel @arestovich --limit 1 --component gemini   # isolate one stage
```

## Architecture

A **ports-and-adapters** monolith. Three cross-cutting decisions explain most of the layout:

**1. Protocols + adapters, with fakes for tests.** Capabilities are `typing.Protocol` interfaces implemented by swappable adapters:
- `storage/interfaces.py` defines repository Protocols (Person, Source, Prediction, VectorStore); `storage/postgres.py` implements them on SQLAlchemy async.
- `sources/base.py` defines the `Source` Protocol; `sources/telegram.py` is the real Telethon adapter, `sources/mock.py` the test one.

Because of this seam, `tests/fakes.py` provides `FakeSourceRepo`/`FakePredictionRepo`, so the whole suite runs with no Docker and no network. When you add a Protocol, add its fake alongside.

**2. Two model layers, bridged explicitly.** `models/domain.py` holds Pydantic domain models (the language of business logic); `models/db.py` holds SQLAlchemy ORM models (persistence). `domain_to_*_db()` functions convert between them. Keep ORM types out of business logic — pass domain models across layer boundaries.

**3. One composition root.** `factory.py::build_orchestrator` builds the engine, repos, LLM/embedding clients, extractor, and Telegram source, wires them into the `IngestionOrchestrator`, and registers teardown on an `AsyncExitStack`. `app.py` (FastAPI) calls it from its `lifespan` and stores the orchestrator on `app.state`; `__main__.py` is the uvicorn entry. The only live endpoints are `GET /health` and `POST /ingest/run` (which runs `orchestrator.run_cycle()`).

Ingestion-cycle flow: `IngestionOrchestrator.run_cycle()` (`ingestion/orchestrator.py`) iterates active sources → collects posts → `PredictionExtractor` (`analysis/extractor.py`) pulls claims via the LLM → persists through the repos → returns a `CycleReport`/`ChannelReport` (`ingestion/report.py`). `PredictionVerifier` (`analysis/verifier.py`) checks claims against evidence and is the most actively-iterated component (4-status confirmed/refuted/unresolved/premature design — see `docs/verification-track/` and `docs/verifier-v2/`).

**LLM access is provider-agnostic via LiteLLM.** `llm/client.py` (`LLMClient`, completion) and `llm/embedding.py` (`EmbeddingClient`) wrap LiteLLM; prompt templates live in `llm/prompts.py`. Don't import a vendor SDK directly — go through these. Model is chosen via `.env` (`config.py` defaults to `openai/gpt-4o-mini`); evals selected Gemini 3.1 Flash Lite as the production extraction model.

**Eval scripts share production code — do not fork it.** `scripts/` holds the evaluation pipelines (detection benchmark, extraction-quality LLM-as-judge, verification eval). They import the *same* extractor classes and the *same* prompts from `src/` and run them in a different mode. This is deliberate: a separate eval prompt would let "eval says the model is good" diverge from production behavior. Change a prompt or extractor once and both move together. Eval inputs live in `scripts/data/`, outputs in `scripts/outputs/`. Scripts are grouped into domain packages — `scripts/{ingestion,extraction,verification}/` (each with `__init__.py`); cross-imports are package-qualified (e.g. `from extraction.detection_eval import ...`).

## Conventions

- **Async-first tests**: `pytest` with `asyncio_mode = "auto"` — write `async def test_...` with no marker. `pythonpath` covers `src`, `scripts`, `tests` (so eval scripts and `tests/fakes.py` import cleanly).
- **Migrations**: any change to `models/db.py` needs an Alembic revision; the schema uses pgvector, so the Postgres container must be up to autogenerate/apply.
- **Config**: everything flows through `config.py` (`pydantic-settings`, reads `.env`). `extra="ignore"` lets eval-only keys (e.g. `ANTHROPIC_API_KEY`) live in `.env` without bloating the schema.
- **Commits**: history uses `type(scope): subject` (conventional commits), written in Ukrainian.
- **Never commit**: `.env` and the Telethon `tg_session*` file (a logged-in account session).

## Design docs are the source of truth (read before building)

This project practices spec-driven development. Non-trivial work is specced as a **`design.md` + `plan.md` pair** inside a use-case subfolder of `docs/` (e.g. `docs/verifier-v2/`, `docs/ingestion-to-aws/`, `docs/verification-track/`), filenamed `YYYY-MM-DD-<topic>.md` by creation date. Before implementing in an area, read that area's design + plan first, and follow the same design → plan → TDD flow for new work.

Living indexes to orient from:
- `docs/README.md` — index of all doc tracks.
- `docs/architecture/2026-04-26-architecture-current.md` — module inventory, the 7 data flows, what's built vs. designed.
- `progress.md` (repo root) — project-wide progress log; per-track status in each `docs/<track>/README.md`.

Most docs are written in Ukrainian. `progress.md` (project root) is the project-wide progress log — time, cost, milestones; `architecture-current.md` holds module/flow detail and the per-track READMEs hold per-task detail.
