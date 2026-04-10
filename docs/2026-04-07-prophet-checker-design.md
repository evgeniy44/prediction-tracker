# Prophet Checker — Design Specification

**Date:** 2026-04-07
**Status:** Draft
**Project:** Pet project — AI-powered analysis of public figures' predictions

---

## Overview

Prophet Checker is a Telegram bot that analyzes predictions made by Ukrainian public figures (politicians, experts, analysts) since 2012. It collects statements from multiple sources, extracts predictions using LLM, verifies them against real events, and provides an interactive chat interface for querying results.

---

## Tech Stack


| Layer            | Technology                    | Rationale                                       |
| ---------------- | ----------------------------- | ----------------------------------------------- |
| Language         | Python 3.11+                  | Richest AI/LLM ecosystem                        |
| Web Framework    | FastAPI + Uvicorn             | Async, lightweight, de-facto for AI services    |
| LLM Abstraction  | LiteLLM                       | Vendor-agnostic: OpenAI, Anthropic, open-source |
| Database         | PostgreSQL + pgvector         | Structured data + vector search, AWS RDS        |
| ORM              | SQLAlchemy 2.0                | Async support, mature, type-safe                |
| Bot              | python-telegram-bot / aiogram | Telegram Bot API integration                    |
| Deployment       | Docker → EC2 (t3.micro)      | Cost-effective start, easy migration to ECS/EKS |
| Database Hosting | AWS RDS (db.t4g.micro)        | ~$12/mo, managed PostgreSQL                     |

---

## Architecture

Monolith-first FastAPI application with five modules and clean separation of concerns.

```
┌─────────────────────────────────────────────────────────────┐
│                        User (Telegram)                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                        │
│                                                              │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌───────────┐  │
│  │   bot/   │  │ analysis/ │  │ sources/ │  │    llm/   │  │
│  │          │  │           │  │          │  │           │  │
│  │ Telegram │  │ Prediction│  │ Telegram │  │ LiteLLM   │  │
│  │ handlers │  │ extractor │  │ Collector│  │ abstrac-  │  │
│  │ Conver-  │  │ Verifica- │  │ News     │  │ tion      │  │
│  │ sation   │  │ tion      │  │ Collector│  │ Prompt    │  │
│  │ flow     │  │ engine    │  │ Source   │  │ templates │  │
│  └──────────┘  └───────────┘  │ interface│  └───────────┘  │
│                               └──────────┘                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              storage/ — Abstraction Layer              │  │
│  │                                                        │  │
│  │  Interfaces (Protocol/ABC):                            │  │
│  │  PredictionRepository │ VectorStore │ SourceRepository  │  │
│  │                                                        │  │
│  │  Implementations:                                      │  │
│  │  PostgresRepository (SQLAlchemy + pgvector) — prod     │  │
│  │  SQLiteRepository (future) — dev/testing               │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
  Data Sources         PostgreSQL+pgvector    LLM Providers
  (Telegram API,       (AWS RDS)             (OpenAI, Anthropic,
   News RSS/Scraper,                          Open Source
   YouTube [future])                          via LiteLLM)
```

### Module Responsibilities

**bot/** — Telegram Bot interface. Handles user messages, manages conversation flow, formats responses. Design deferred to later phase.

**analysis/** — Core AI pipeline:

- **Prediction Extractor** — LLM-based extraction of predictions from raw text (date, claim, subject, context)
- **Verification Engine** — cross-references predictions against news/facts, assigns status (confirmed / refuted / unresolved) with confidence score
- **Confidence Scoring** — when confidence is low, flags prediction for manual review (human-in-the-loop)

**sources/** — Pluggable data collectors. Each source implements a common interface:

```python
class Source(Protocol):
    async def collect(self, person: str, date_from: date, date_to: date) -> list[RawDocument]: ...
```

- TelegramCollector — collects posts from public Telegram channels
- NewsCollector — RSS feeds and/or web scraping of Ukrainian news sites
- Extensible: YouTube, Twitter/X added later by implementing the same interface

**llm/** — Abstraction over LLM providers via LiteLLM:

- Provider-agnostic API calls
- Prompt templates for prediction extraction and verification
- Configuration per provider (model, temperature, token limits)

**storage/** — Database abstraction layer:


| Interface              | Purpose                                               |
| ---------------------- | ----------------------------------------------------- |
| `PredictionRepository` | CRUD for predictions, filtering by person/date/status |
| `VectorStore`          | Store and query embeddings for RAG semantic search    |
| `SourceRepository`     | CRUD for raw source documents and metadata            |

All business logic depends only on interfaces. Concrete implementation injected at startup via configuration.

---

## Data Model

```
┌─────────────┐     ┌──────────────────┐
│   Person    │     │  PersonSource    │
│─────────────│     │──────────────────│
│ id          │◄──┐ │ id               │
│ name        │   └─│ person_id (FK)   │
│ description │     │ source_type      │
│ created_at  │     │ source_identifier│
└─────────────┘     │ enabled          │
                    └──────────────────┘

┌──────────────────┐     ┌─────────────────┐
│  RawDocument     │     │   Prediction    │
│──────────────────│     │─────────────────│
│ id               │◄──┐ │ id              │
│ person_id (FK)   │   └─│ document_id(FK) │
│ source_type      │     │ person_id (FK)  │
│ url              │     │ claim_text      │
│ published_at     │     │ prediction_date │
│ raw_text         │     │ target_date     │
│ language         │     │ topic           │
│ collected_at     │     │ status          │
└──────────────────┘     │ (confirmed/     │
                         │  refuted/       │
                         │  unresolved)    │
                         │ confidence      │
                         │ evidence_url    │
                         │ evidence_text   │
                         │ verified_at     │
                         │ embedding (vec) │
                         └─────────────────┘
```

**Key relationships:**

- `Person` 1:N `PersonSource` — a person can be tracked across multiple source types
- `PersonSource` decouples person from source details (Telegram channel, RSS URL, YouTube channel ID)
- `Person` 1:N `RawDocument` — raw collected texts linked to person
- `RawDocument` 1:N `Prediction` — one document can contain multiple predictions
- Last collection date for a person+source pair is derived from `MAX(RawDocument.collected_at)`, not stored redundantly

---

## Data Flow

### Ingestion Pipeline

```
Scheduler (periodic)
    │
    ▼
Collector (per source type)
    │ Reads PersonSource for enabled person+source pairs
    │ Collects new documents since last collected_at
    │ Deduplicates by URL
    │ Stores RawDocument
    ▼
LLM: Extract Predictions
    │ Takes unprocessed RawDocuments
    │ Extracts structured predictions:
    │   claim_text, prediction_date, target_date, topic
    │ One document → 0..N predictions
    │ Generates embedding per prediction
    │ Stores Prediction + embedding
    ▼
LLM: Verify Predictions
    │ Separate process (can be deferred)
    │ Searches news sources for confirmation/refutation
    │ Assigns: status + confidence (0.0-1.0)
    │ Stores evidence_url + evidence_text
    │ confidence < 0.6 → status "unresolved" (human review queue)
    ▼
Done — predictions available for chat queries
```

**Key decisions:**

- Extraction and Verification are **two separate stages** — verification can be re-run when new data becomes available
- Verification can be delayed — a prediction about "summer 2023" can only be verified after summer 2023
- All LLM calls go through `llm/` module which logs prompt/response for debugging and cost tracking

### Chat Flow

```
User question (Telegram)
    │
    ▼
Generate embedding for query
    │
    ▼
pgvector semantic search → relevant predictions
    │
    ▼
LLM: Generate answer with context (RAG)
    │ Includes: predictions, sources, confidence scores
    │ Always cites evidence URLs
    │ Adds disclaimer about automated analysis
    ▼
Formatted response → Telegram
```

---

## AWS Infrastructure

```
┌─────────────────────────────────────┐
│            AWS VPC                   │
│                                      │
│  ┌────────────────┐  ┌───────────┐  │
│  │ EC2 t3.micro   │  │ RDS       │  │
│  │                │  │ t4g.micro │  │
│  │ Docker Compose │──│           │  │
│  │ - FastAPI app  │  │ PostgreSQL│  │
│  │ - (all modules)│  │ + pgvector│  │
│  └────────────────┘  └───────────┘  │
│                                      │
└─────────────────────────────────────┘

Estimated monthly cost:
  EC2 t3.micro  — free tier (year 1) or ~$8/mo
  RDS t4g.micro — ~$12/mo
  LLM API calls — variable, ~$5-20/mo depending on usage
  Total: ~$20-40/mo
```

---

## Key Design Decisions

1. **Pluggable sources** — each data source implements `Source` interface; adding YouTube/Twitter later requires zero changes to analysis or bot modules
2. **LiteLLM abstraction** — switch between OpenAI/Claude/open-source with a config change; enables cost optimization and A/B testing of models
3. **Repository pattern** — business logic decoupled from PostgreSQL via Protocol/ABC interfaces; enables testing with in-memory implementations and future DB migration
4. **PersonSource decoupling** — person entity is source-agnostic; new sources added without changing Person model
5. **RAG pipeline** — pgvector for semantic search across predictions when answering chat queries
6. **Hybrid verification** — AI verifies with mandatory source links; low-confidence results queued for human review
7. **Two-stage ingestion** — extraction and verification are separate; verification can be deferred and re-run independently

---

## Scope

### In scope (MVP)

- Telegram and news site data collection
- LLM-based prediction extraction from Ukrainian text
- Automated verification with confidence scoring
- Telegram bot with RAG-powered Q&A
- PostgreSQL + pgvector on AWS RDS
- Docker deployment on EC2

### Deferred

- Bot interaction design (commands, response format)
- YouTube and Twitter/X collectors
- SQLite repository for local dev
- Manual review UI for low-confidence predictions
- Migration to ECS/EKS

---

## Target Public Figures (Initial)

Ukrainian politicians and experts with extensive public prediction history since 2012:

- Arestovych, Piontkovskiy, and similar figures
- Focus on geopolitical and war-related predictions
- Sources primarily in Ukrainian language
