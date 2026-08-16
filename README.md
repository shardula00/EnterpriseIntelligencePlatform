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
| 6 | MLOps hardening — model registry, drift detection, performance monitoring, alerting |
| 7 | GenAI/RAG foundation — embeddings, pgvector retrieval, configurable LLM provider |
| 8 | NL analytics — Text-to-SQL, AI explanations, answer evaluation |
| 9 | Knowledge graph — entities/relationships, hybrid RAG+KG retrieval |
| 10 | Multi-agent workflows — Data/Analytics/ML/Research/Decision/Risk agents |
| 11 | Decision intelligence — recommendations, risk scoring, what-if simulation, approvals |
| 12 | Hardening — full test suite, Docker packaging, CI/CD pipelines, security review |
| 13 | Cloud deployment — minimal-cost AWS (**current**) |
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
├── backend/                 — FastAPI app: ingestion (2), KPIs (3), auth/RBAC/audit (4), classical ML (5), MLOps (6), RAG (7), NL analytics (8), knowledge graph (9), agents (10), decisions (11); backend/Dockerfile, backend/SECURITY.md checks (12)
├── frontend/                — React + TS + Vite + Tailwind app, auth-aware, one page/section per phase above; frontend/Dockerfile (12)
├── data/                    — local dataset/artifact/document working area (gitignored contents)
├── infra/                   — docker-compose.yml (Postgres/pgvector + backend + frontend, Phase 12); infra/aws/ (EC2 deployment runbook + files, Phase 13)
├── SECURITY.md               — RBAC coverage, secrets handling, dependency audit results, accepted risks (Phase 12); production deployment security notes (Phase 13)
└── docs/                    — ADRs and diagrams as they accumulate
```

## Status

**Phase 13 — Cloud Deployment (AWS), infrastructure files prepared, not yet deployed.**
Phases 1–12 (data platform, BI, auth/RBAC, classical ML, MLOps, RAG, NL
analytics, knowledge graph, multi-agent workflows, decision intelligence,
testing/security/CI/CD hardening) are complete, tested, and unchanged by
this phase. Phase 13 deploys the exact same containers Phase 12 already
builds to a single AWS EC2 instance, at minimal cost:

- **Compute**: one EC2 `t3.small` instance running the same three
  containers as local dev (Postgres+pgvector, backend, frontend) plus a
  Caddy reverse proxy for automatic HTTPS — no RDS, no ECS/Fargate, no
  Kubernetes/EKS, no ALB. See [infra/aws/README.md](infra/aws/README.md)
  for the full runbook and exact AWS resources.
- **Secrets**: AWS SSM Parameter Store in production (not `.env`) — local
  development is completely unchanged and still uses `infra/.env`/
  `backend/.env` exactly as before.
- **No SSH**: administrative access is via AWS SSM Session Manager only;
  the security group never opens port 22.
- **Deploys** run via GitHub Actions (`.github/workflows/deploy.yml`),
  authenticated to AWS via OIDC (no long-lived AWS keys as GitHub
  secrets), triggered manually (`workflow_dispatch`) — never automatically
  on push, since this touches a real running system and real cost.
- **Backup/rollback**: a daily `pg_dump` + app-data backup on the
  instance, with a documented procedure
  ([infra/aws/ROLLBACK.md](infra/aws/ROLLBACK.md)) to restore a backup
  back into local Docker Compose — the platform can always return to
  local-only without data loss.
- **Cost monitoring**: an AWS Budgets alert (monthly limit is a
  placeholder in `infra/aws/budget.json` until a real limit is provided).
- **Nothing has been deployed yet.** `infra/aws/` contains every file
  needed, but no AWS resource has been created — see that directory's
  README for the exact manual steps and what's still needed from you
  (AWS account access, a domain for HTTPS, the budget limit) before
  anything goes live.

See [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) for the full history.

## Running the full stack with Docker Compose

```powershell
cd infra
cp .env.example .env      # defaults work as-is for local dev
docker compose up -d --build
```

This starts three containers on the `eip` Compose network:

| Service | Reachable at | Healthcheck |
|---|---|---|
| `postgres` | `localhost:5432` | `pg_isready` |
| `backend` | `http://localhost:8000` | `GET /health` (checks real DB connectivity, not just process liveness) |
| `frontend` | `http://localhost:8080` | `GET /healthz` (nginx) |

`backend` waits for `postgres` to be healthy before starting (applies
Alembic migrations, then optionally bootstraps the first admin user if
`BOOTSTRAP_ADMIN_PASSWORD` is set — see `infra/.env.example`); `frontend`
waits for `backend`. Uploaded datasets and ML/RAG artifacts persist in the
repo's own `data/` directory (bind-mounted), the same location used
outside Docker. Tear down with `docker compose down` (add `-v` to also
drop the Postgres volume).

This is local-only bring-up — no image is pushed to any registry.

## Cloud deployment (Phase 13)

The same containers this section starts locally can be deployed to a
single AWS EC2 instance — see
[infra/aws/README.md](infra/aws/README.md) for the complete runbook
(exact AWS resources, IAM policies, SSM parameter setup, and what's still
needed from you before anything is created) and
[infra/aws/ROLLBACK.md](infra/aws/ROLLBACK.md) for restoring a production
backup back into this local Docker Compose setup. Local development is
entirely unaffected — it still uses `infra/.env`/`backend/.env`, never SSM.

## Security checks, coverage, and dependency audits

See [SECURITY.md](SECURITY.md) for the full writeup (RBAC coverage,
secrets handling, accepted tradeoffs, current audit results). To re-run
everything locally:

```powershell
# Backend (from backend/, venv active)
.venv\Scripts\pytest --cov=app --cov-report=term-missing --cov-report=html  # coverage
.venv\Scripts\pytest tests/rbac/test_route_coverage.py -v                    # RBAC route coverage
.venv\Scripts\pip-audit -r requirements.txt                                  # dependency audit

# Frontend (from frontend/)
npm run test:coverage   # coverage
npm audit                # dependency audit
```

Both also run automatically in CI (`.github/workflows/backend-ci.yml`,
`.github/workflows/frontend-ci.yml`) on every push — coverage and audit
results are uploaded/printed as part of the job, not gated as a hard
pass/fail threshold (see [SECURITY.md](SECURITY.md) for why).

## Local development principles

- The system must run entirely locally (Docker Compose) before any cloud
  deployment is considered.
- Cloud costs should stay near zero during development.
- Secrets are always environment variables, never hard-coded, never committed.
- Every dependency added must have a clear, stated reason.
- Every phase leaves the application in a working, demonstrable state.
