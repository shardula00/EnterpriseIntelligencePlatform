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
│  Validation         Registry (MLflow) Agents            │
│  ETL                Prediction        Knowledge Graph   │
│  Storage            Monitoring        Text-to-SQL        │
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
| 4 | Auth & RBAC — users, roles, permissions, audit log (**current**) |
| 5 | Classical ML — churn, forecasting, segmentation, anomaly detection, MLflow |
| 6 | MLOps hardening — monitoring, drift detection, serving |
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
| MLOps | MLflow | Free, local-first experiment tracking and model registry |
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
├── backend/                 — FastAPI app: ingestion (Phase 2), KPI engine (Phase 3), auth/RBAC/audit (Phase 4)
├── frontend/                — React + TS + Vite + Tailwind app (Phase 3), auth-aware (Phase 4)
├── data/                    — local dataset working area (gitignored contents)
├── infra/                   — docker-compose.yml (Postgres + pgvector)
└── docs/                    — ADRs and diagrams as they accumulate
```

## Status

**Phase 4 — Authentication, RBAC & Audit Logging.** The platform is now a
real multi-user application: register or log in, and every dataset/KPI/
user/audit route requires a valid session and the right permission -
enforced server-side, not just hidden in the UI. Three roles (Admin,
Analyst, Viewer) with a fine-grained permission catalog; an admin console
for managing users and roles; a queryable audit log of every
security-relevant action. All of Phase 1–3's ingestion, KPI, and dashboard
functionality keeps working exactly as before, now behind that boundary.
See [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) for what comes next.

## Local development principles

- The system must run entirely locally (Docker Compose) before any cloud
  deployment is considered.
- Cloud costs should stay near zero during development.
- Secrets are always environment variables, never hard-coded, never committed.
- Every dependency added must have a clear, stated reason.
- Every phase leaves the application in a working, demonstrable state.
