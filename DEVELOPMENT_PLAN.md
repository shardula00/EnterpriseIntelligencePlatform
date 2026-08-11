# Development Plan

Phased implementation plan for the Enterprise Intelligence & Autonomous
Decision Platform. Each phase has an objective, concrete deliverables, and a
definition of done. **A phase is not complete until the definition of done
is met and the system still runs end-to-end.** Phases are sequential; we do
not start phase N+1 work before phase N is approved.

This plan will be refined as we go — later phases are described at a
coarser grain than near-term ones, and will be detailed just before they
start, incorporating whatever we learned in earlier phases.

---

## Phase 0 — Project Foundation (current)

**Objective:** Establish repository structure, documentation, and shared
understanding before writing any application code.

**Deliverables:**
- `README.md`, `ARCHITECTURE.md`, `DEVELOPMENT_PLAN.md`
- `.gitignore`, `.python-version`
- Empty `backend/`, `frontend/`, `data/`, `infra/`, `docs/` directories with
  placeholder READMEs
- Git repository initialized with an initial commit

**Definition of done:** Repo structure exists, docs explain the vision,
architecture, and plan clearly enough that a third party (or future you)
could pick up the project from them alone. No frontend/backend code yet.

---

## Phase 1 — Local Infrastructure & Backend Skeleton

**Objective:** A running, empty-but-real backend: containerized Postgres
with pgvector, a FastAPI app with a health-check endpoint, database
migrations, and a CI pipeline that lints and tests it.

**Deliverables:**
- `infra/docker-compose.yml`: Postgres (pgvector extension enabled)
  container, `.env.example` for local config
- `backend/`: FastAPI app (`app/main.py`), Pydantic settings loaded from
  environment variables, SQLAlchemy engine/session setup, Alembic migration
  scaffold, `pyproject.toml`/`requirements.txt`
- `GET /health` endpoint returning app + DB connectivity status
- One real Alembic migration (even if it's just a placeholder table) to
  prove the migration pipeline works
- `pytest` configured with at least one passing test (e.g. health check via
  `httpx`/`TestClient`)
- GitHub Actions workflow: install deps, run linter, run pytest, on every
  push/PR

**Definition of done:** `docker compose up` brings up Postgres; the FastAPI
app connects to it, migrations apply cleanly, `/health` returns 200, tests
pass locally and in CI.

**This is the first MVP** — see "First MVP" section below for why this
scope, not a bigger one.

---

## Phase 2 — Data Platform: Ingestion & Quality

**Objective:** Turn raw uploaded files into validated, profiled,
quality-scored relational data with lineage.

**Deliverables:**
- Upload endpoints for CSV, Excel (`.xlsx`), JSON
- Schema detection (column types, nullability) on upload
- Data profiling (row counts, null rates, distinct counts, basic stats per
  column)
- Validation rules + a data quality score per dataset
- Transformation step (e.g. type coercion, basic cleaning) recorded as
  lineage metadata (what source produced what table, when, via what steps)
- Tests: unit tests for schema detection/profiling logic, integration tests
  for the upload → stored-table flow

**Definition of done:** Uploading a sample CSV/Excel/JSON file via the API
results in a queryable Postgres table, a stored profile/quality report, and
a lineage record — all verifiable via API responses and tests.

---

## Phase 3 — Business Intelligence Layer & Frontend Introduction

**Objective:** First user-facing surface. A React/TypeScript/Vite/Tailwind
frontend rendering configurable KPIs and dashboards from real ingested data.

**Deliverables:**
- `frontend/`: Vite + React + TS + Tailwind scaffold, typed API client
  generated from/matched to the backend OpenAPI schema
- Backend: KPI computation endpoints (revenue, profit, customer/product/
  marketing/inventory metrics where the ingested schema supports them),
  configurable KPI definitions (not hard-coded per dataset)
- Frontend: dashboard page(s) with interactive charts over the ingested
  data
- Frontend tests (component/interaction tests for at least the dashboard)

**Definition of done:** A user can upload a dataset (Phase 2) and see it
reflected in configurable KPI dashboards in the browser, with both backend
and frontend tests passing.

---

## Phase 4 — Authentication & RBAC

**Objective:** Real multi-user security instead of an open API.

**Deliverables:**
- User model, JWT-based login/auth
- Roles and permissions (e.g. viewer/analyst/admin), enforced at the API
  layer via dependency injection
- Audit log of sensitive actions (uploads, model actions, decisions —
  extended in later phases)
- Frontend: login flow, route protection by role
- Tests: auth flow, permission enforcement (positive and negative cases)

**Definition of done:** Unauthenticated requests are rejected; role-gated
endpoints correctly allow/deny based on role; audit log records key actions.

---

## Phase 5 — Classical Machine Learning

**Objective:** Real predictive models, tracked and served properly, not
notebook-only experiments.

**Deliverables:**
- MLflow wired into Docker Compose (tracking server + registry backend)
- Churn prediction model (classification)
- Sales forecasting model (regression/time-series)
- Customer segmentation (clustering)
- Anomaly detection
- Each model: training script logged to MLflow, evaluation metrics
  recorded, best version registered
- API endpoints to serve predictions from the registered model version
- Tests: training pipeline tests, prediction endpoint tests

**Definition of done:** Each model can be retrained via a documented
command, its run appears in MLflow with metrics, and its predictions are
servable via the API against real ingested data.

---

## Phase 6 — MLOps Hardening

**Objective:** Move from "a model that works once" to "a model system that
can be trusted over time."

**Deliverables:**
- Model versioning/promotion workflow (staging → production in registry)
- Basic data drift detection (comparing incoming data distribution to
  training distribution)
- Basic model performance monitoring over time
- Alerting/logging when drift or degradation is detected

**Definition of done:** Feeding the system a deliberately shifted dataset
triggers a detectable drift signal, visible via API/logs.

---

## Phase 7 — Generative AI & RAG Foundation

**Objective:** Ground LLM answers in real enterprise documents/data, with a
provider-agnostic, mostly-local setup.

**Deliverables:**
- Document ingestion pipeline (chunking) into pgvector
- Embedding generation via a Hugging Face model (local)
- LLM provider abstraction: local model support (e.g. via Ollama or a
  small HF model) as default, hosted API as opt-in config
- Retrieval endpoint: query → relevant chunks → LLM-generated answer with
  citations back to source chunks
- Tests: retrieval relevance sanity checks, citation-presence checks

**Definition of done:** Asking a question answerable from ingested
documents returns a grounded answer with citations, running entirely on
local/free components by default.

---

## Phase 8 — Natural-Language Business Analytics

**Objective:** Let users ask business questions in plain English against
structured data, not just documents.

**Deliverables:**
- Text-to-SQL: NL question → generated SQL → safe execution (read-only,
  scoped) → result
- AI-generated explanation of the result, combining structured results and
  RAG-retrieved context where relevant
- Answer evaluation: automated checks (e.g. does the SQL execute, does the
  explanation cite its evidence) before returning an answer
- Tests: a fixed set of NL questions with expected SQL/result shape

**Definition of done:** A defined set of representative business questions
produce correct, cited, evaluated answers end-to-end.

---

## Phase 9 — Knowledge Graph & Hybrid Retrieval

**Objective:** Add structured entity/relationship knowledge alongside
vector retrieval, built so the two retrieval modes can be toggled
independently — the prerequisite for the eventual research comparison.

**Deliverables:**
- Entity/relationship model for core enterprise concepts (customer,
  product, order, etc.), stored relationally in Postgres initially (see
  ARCHITECTURE.md §7 for the graph-DB decision point)
- Graph population from ingested data
- Hybrid retrieval: RAG + KG combined, with a config flag to run
  vector-only for comparison
- Tests: retrieval correctness for graph-answerable questions

**Definition of done:** The same question can be answered via vector-only
retrieval or hybrid retrieval by config, with visibly different (and for
graph-answerable questions, more accurate) results.

---

## Phase 10 — Multi-Agent Workflows

**Objective:** Compose the now-existing capabilities (ingestion, ML
serving, RAG, KG, BI) via specialized agents rather than one monolithic
prompt.

**Deliverables:**
- Agent definitions: Data, Analytics, ML, Research, Visualization,
  Decision, Risk — each with a scoped tool surface over existing APIs
- An orchestration layer routing a user request to the right agent(s)
- Tests: scenario-based tests per agent

**Definition of done:** A complex request that spans multiple domains
(e.g. "forecast next quarter's revenue and flag any risk factors") is
correctly decomposed and answered by the appropriate agents.

---

## Phase 11 — Decision Intelligence

**Objective:** Turn analysis into actionable, accountable decisions.

**Deliverables:**
- Recommendation generation from ML + AI outputs
- Risk scoring
- What-if simulation (parameterized scenario runs)
- Scenario comparison view
- Human-in-the-loop approval workflow before a recommendation is marked
  "acted on," logged to the audit trail

**Definition of done:** A recommendation can be generated, simulated under
alternative scenarios, and explicitly approved or rejected by a user, with
the full trail recorded.

---

## Phase 12 — Full Testing, Security & CI/CD Hardening

**Objective:** Bring the whole system's engineering quality to a
portfolio-defensible standard.

**Deliverables:**
- Expanded unit/integration/API/frontend test coverage across all phases
- Security review pass (RBAC coverage, secrets handling, dependency audit)
- Full Docker Compose bring-up of every service
- Complete CI/CD pipelines (build, test, lint, image build) for backend and
  frontend

**Definition of done:** `docker compose up` runs the entire platform from a
clean checkout; CI is green; a documented security checklist is satisfied.

---

## Phase 13 — Cloud Deployment (AWS)

**Objective:** Deploy the already-stable local system to AWS at minimal
cost.

**Deliverables:**
- Containerized deployment (exact services TBD based on cost — likely
  ECS/Fargate or a single EC2 instance rather than anything cluster-heavy)
- Cost monitoring/budget alerts
- Production configuration (secrets via a proper secrets manager, not
  `.env`)

**Definition of done:** The platform is reachable at a public URL, costs
are within an explicitly agreed budget, and rollback to local-only is
possible without data loss.

---

## Phase 14+ — Research Component (deferred, opt-in)

**Objective (not started now):** Use the hybrid RAG+KG infrastructure built
in Phase 9 to empirically evaluate:

> Does combining vector-based RAG with structured enterprise knowledge
> graphs improve the accuracy, groundedness, and reliability of AI-driven
> enterprise analytics compared with vector-only RAG?

This requires defining an evaluation dataset, metrics (accuracy,
groundedness, citation correctness), and a methodology — all deferred until
Phase 9 exists and we can scope this properly as its own mini-project.

---

## First MVP — what it is and why

The first MVP is the **end of Phase 1**: a containerized Postgres database
with pgvector enabled, a FastAPI backend with health-checking and working
database migrations, and a CI pipeline that proves the whole thing is
tested automatically.

This is deliberately not "a feature a user would care about." It's the
smallest slice that proves the foundational plumbing — container
orchestration, database connectivity, migrations, dependency management,
automated testing — all works together, on Windows, before any real
feature is built on top of it. Every later phase depends on this plumbing
being solid; debugging it under the weight of real features would be much
harder than debugging it now, alone.

The first **user-visible** MVP follows in Phase 3, once there's ingested
data (Phase 2) worth looking at on a dashboard.

## How we work through phases

1. I explain what a phase involves and why, before writing code.
2. I implement the phase's deliverables incrementally, explaining non-obvious
   choices as they come up.
3. I do not introduce a phase's technology before that phase starts.
4. Each phase ends with: a summary of what was built, how to run/verify it,
   and what's proposed for the next phase — then I wait for approval.
5. Architectural changes that affect more than the current phase are
   explained and confirmed before implementation, not after.
