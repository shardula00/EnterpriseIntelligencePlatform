# Enterprise Intelligence & Autonomous Decision Platform

An MSc-level portfolio project: a production-style enterprise analytics and
decision-support platform combining data engineering, classical ML,
generative AI/RAG, knowledge graphs, multi-agent workflows, business
intelligence, and decision intelligence — built incrementally, with a
working system at every milestone.

## Vision

Most portfolio projects are either a toy ML notebook or a toy CRUD app. This
project is neither. It is meant to demonstrate, end to end, how a real
enterprise analytics platform is designed and built:

- ingesting messy real-world data and turning it into trustworthy metrics,
- applying classical ML where classical ML is the right tool,
- applying generative AI (RAG, NL-to-SQL, agents) where language
  understanding is the right tool,
- wrapping both in the software engineering discipline (tests, CI/CD,
  security, observability) that separates a demo from a system,
- and supporting actual decisions (recommendations, risk scoring, what-if
  simulation) rather than just dashboards.

It should be explainable in an interview end-to-end, and it should be
extensible into a genuine research contribution (see below), not just a
technology showcase.

## What this is not

- Not a race to use the most technologies. Every dependency in this repo
  must earn its place — see [ARCHITECTURE.md](ARCHITECTURE.md) for the
  reasoning behind each choice, and the "not yet" list for what is
  deliberately excluded until there's a real reason to add it.
- Not built in one shot. It is built in explicit phases, each leaving the
  system runnable and demonstrable. See [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md).

## High-level architecture

```
Users
  ↓
React Frontend (TypeScript, Vite, Tailwind)
  ↓
API Layer (FastAPI)
  ↓
Authentication & Authorization (RBAC)
  ↓
Application Services
  ↓
┌─────────────────────────────────────────────────────┐
│  Data Platform     ML Platform       AI Platform      │
│  ─────────────     ──────────        ───────────      │
│  Ingestion          Training          RAG              │
│  Validation         Native registry   Agents            │
│  ETL                Prediction        Knowledge Graph   │
│  Storage            Drift/monitoring  Text-to-SQL        │
└─────────────────────────────────────────────────────┘
  ↓
PostgreSQL (+ pgvector)
  ↓
MLOps / Docker / CI-CD
  ↓
AWS deployment (later, minimal cost)
```

Full reasoning, component responsibilities, and data flow are in
[ARCHITECTURE.md](ARCHITECTURE.md).

## Roadmap (phase summary)

| Phase | Focus |
|---|---|
| 0 | Project foundation — docs, repo skeleton |
| 1 | Local infra & backend skeleton — Docker Compose, Postgres/pgvector, FastAPI, CI |
| 2 | Data platform — ingestion, schema detection, profiling, quality, lineage |
| 3 | BI layer — KPI engine, React/Vite/Tailwind dashboards |
| 4 | Auth & RBAC — users, roles, permissions, audit log |
| 5 | Classical ML — churn, forecasting, segmentation, anomaly detection |
| 6 | MLOps hardening — model registry, drift detection, performance monitoring, alerting (**current**) |
| 7 | GenAI/RAG foundation — embeddings, pgvector retrieval, configurable LLM provider |
| 8 | NL analytics — Text-to-SQL, AI explanations, answer evaluation |
| 9 | Knowledge graph — entities/relationships, hybrid RAG+KG retrieval |
| 10 | Multi-agent workflows — Data/Analytics/ML/Research/Visualization/Decision/Risk agents |
| 11 | Decision intelligence — recommendations, risk scoring, what-if simulation, approvals |
| 12 | Hardening — full test suite, Docker packaging, CI/CD pipelines |
| 13 | Cloud deployment — minimal-cost AWS |
| 14+ | Research component (opt-in, later) |

Full detail, deliverables, and definition-of-done per phase: see
[DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md).

## Research component (deferred)

The platform is designed so that, once the RAG (Phase 7) and knowledge graph
(Phase 9) components exist, it can support an MSc research question:

> Does combining vector-based RAG with structured enterprise knowledge
> graphs improve the accuracy, groundedness, and reliability of AI-driven
> enterprise analytics compared with vector-only RAG?

This is **not** implemented now. It is a design constraint on Phases 7–9
(both retrieval paths must be independently swappable so they can later be
evaluated against each other), not a current deliverable.

## Technology choices (summary)

| Layer | Choice | Why |
|---|---|---|
| Frontend | React + TypeScript + Vite + Tailwind | Industry-standard, fast local dev, typed |
| Backend | Python + FastAPI + Pydantic + SQLAlchemy | Async-friendly, typed, auto OpenAPI docs |
| Database | PostgreSQL + pgvector | One database for relational *and* vector data — no separate vector DB needed at this scale |
| Data/ML | Pandas, NumPy, scikit-learn, XGBoost, PyTorch (where justified) | Standard, well-supported, free |
| AI | Hugging Face, configurable LLM provider, local LLM support, RAG | Avoids lock-in to a single paid API |
| MLOps | Native registry (Phase 6) — `ModelVersion`/`MonitoringEvent` tables, PSI-based drift, per-task performance checks | No MLflow needed: the registry only tracks this platform's own runs, joined to existing `ml_runs` data with zero new infrastructure |
| CI/CD | GitHub Actions + Docker | Free tier is sufficient for a solo project |
| Cloud | AWS (later, after local system is stable) | Deferred until there's something worth deploying |

Full rationale for every choice, and the explicit "not yet" list (Kafka,
Spark, Kubernetes, Neo4j, paid APIs by default, etc.), is in
[ARCHITECTURE.md](ARCHITECTURE.md).

## Repository layout (current)

```
EnterpriseIntelligencePlatform/
├── README.md              — this file
├── ARCHITECTURE.md         — architecture & technology rationale
├── DEVELOPMENT_PLAN.md      — phased implementation plan
├── .gitignore
├── .python-version          — pins Python 3.12 for the backend/ML environment
├── backend/                 — FastAPI app: ingestion (Phase 2), KPI engine (Phase 3), auth/RBAC/audit (Phase 4), classical ML (Phase 5), MLOps registry/monitoring (Phase 6)
├── frontend/                — React + TS + Vite + Tailwind app (Phase 3), auth-aware (Phase 4)
├── data/                    — local dataset working area (gitignored contents)
├── infra/                   — docker-compose.yml (Postgres + pgvector)
└── docs/                    — ADRs and diagrams as they accumulate
```

## Status

**Phase 6 — MLOps Hardening.** Every completed training run (Phase 5) can
now be registered as a versioned, lineage-preserving model version and
moved through a lifecycle — candidate → staging → production → archived —
enforced both in application code and by a database constraint that allows
at most one production version per dataset/task family. A model version
can be evaluated for data drift (Population Stability Index, against a new
dataset) and performance degradation (real ground-truth metrics for
classification/forecasting, honestly-labeled unsupervised proxy signals
for segmentation/anomaly detection); every check is recorded as a
severity-rated monitoring event, queryable via API and visible on a global
alerts page and each version's own detail page — the foundation for a
future external alert channel, not one itself. Detection never
auto-remediates: retraining or re-promotion stays a separate, explicit,
human action. A `/mlops` section in the frontend extends the existing ML
UI (reusing Phase 5's results components rather than duplicating them),
gated by three new permissions (`mlops:read`, `mlops:evaluate`,
`mlops:promote`). No MLflow, no Celery/Redis — see
[ARCHITECTURE.md](ARCHITECTURE.md) §3.4a for why a native implementation
was sufficient. All of Phase 1–5's functionality — ingestion, KPIs,
auth/RBAC/audit, and all four ML tasks — keeps working exactly as before,
re-verified end-to-end. See [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) for
what comes next.

## Local development principles

- The system must run entirely locally (Docker Compose) before any cloud
  deployment is considered.
- Cloud costs should stay near zero during development.
- Secrets are always environment variables, never hard-coded, never committed.
- Every dependency added must have a clear, stated reason.
- Every phase leaves the application in a working, demonstrable state.
