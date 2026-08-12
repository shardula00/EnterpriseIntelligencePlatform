# Architecture

This document describes the planned architecture of the Enterprise
Intelligence & Autonomous Decision Platform, the reasoning behind each
technology choice, and what is deliberately excluded for now. It will be
updated as each phase lands — this is a living document, not a spec frozen
at project start.

## 1. Guiding principles

1. **Local-first.** The full system must run on a single developer machine
   via Docker Compose before any cloud deployment is considered.
2. **Justify every dependency.** A technology is added when a phase has a
   concrete need for it, not speculatively. See §5 for what's excluded.
3. **One database until proven insufficient.** PostgreSQL handles relational
   data, and pgvector extends it to handle vector similarity search. A
   dedicated vector database (Pinecone, Weaviate, Qdrant, etc.) is only
   introduced if pgvector demonstrably can't keep up — unlikely at portfolio
   scale (thousands to low millions of vectors).
4. **Boring technology where it doesn't matter, interesting technology where
   it's the point.** The auth system, the CRUD layer, the CI pipeline —
   these should be conventional and unremarkable. The RAG/KG hybrid
   retrieval, the multi-agent orchestration, the decision intelligence
   layer — these are where the engineering interest (and the research
   angle) lives.
5. **Every phase ships a working system.** Nothing is merged half-built;
   the previous phase's demo keeps working while the next phase adds to it.

## 2. Layered view

```
Users
  ↓
React Frontend (TypeScript, Vite, Tailwind)
  ↓
API Layer (FastAPI, Pydantic schemas, OpenAPI docs)
  ↓
Authentication & Authorization (JWT, RBAC, audit logging)
  ↓
Application Services (business logic, orchestration)
  ↓
┌───────────────────────────────────────────────────────────┐
│                                                             │
│  Data Platform          ML Platform          AI Platform    │
│  ─────────────          ──────────           ───────────    │
│  - Ingestion            - Training            - RAG           │
│    (CSV/Excel/JSON/API)   (scikit-learn)        (retrieval +    │
│  - Schema detection     - Native registry        generation)   │
│  - Profiling              (versioning +        - Agents          │
│  - Validation &           lifecycle)             (Data/Analytics/│
│    quality scoring      - Prediction serving      ML/Research/  │
│  - Transformation       - Drift detection         Viz/Decision/  │
│  - Lineage tracking     - Perf. monitoring        Risk agents)   │
│                         - Monitoring events     - Knowledge Graph│
│                                                  - Text-to-SQL     │
│                                                                    │
└───────────────────────────────────────────────────────────┘
  ↓
PostgreSQL (relational tables + pgvector embeddings)
  ↓
MLOps / Docker / CI-CD (GitHub Actions)
  ↓
AWS deployment (deferred to Phase 13)
```

Each of the three platform columns (Data, ML, AI) is built as a set of
Python modules inside the single FastAPI backend during early phases —
**not** as separate microservices. Splitting into separate deployable
services is a decision to revisit only if/when it's actually justified
(e.g., independent scaling needs, independent deploy cadence). Premature
service-splitting adds operational complexity (networking, service
discovery, distributed tracing) with no benefit at this scale.

## 3. Component responsibilities

### 3.1 Frontend (`frontend/`, from Phase 3)
React + TypeScript + Vite + Tailwind CSS. Talks to the backend exclusively
through the documented REST API (FastAPI's auto-generated OpenAPI schema
drives a typed API client). No business logic in the frontend beyond
presentation and interaction state.

### 3.2 API layer & application services (`backend/`, from Phase 1)
FastAPI app organized by domain module (e.g. `ingestion`, `bi`, `ml`,
`rag`, `agents`, `auth`), each exposing a router. Pydantic models define
request/response contracts. SQLAlchemy models define persistence. Services
contain business logic and are unit-testable independently of the HTTP
layer.

### 3.3 Data platform
Responsible for getting raw enterprise data (CSV/Excel/JSON, later APIs)
into a validated, profiled, quality-scored relational form, with lineage
metadata describing where every derived value came from. This is the
foundation everything else — BI, ML, RAG — reads from.

### 3.4 ML platform (implemented Phase 5)
Four classical ML tasks — binary classification, time-series forecasting,
customer segmentation, anomaly detection — implemented entirely with
scikit-learn (`backend/app/ml/`). No XGBoost/PyTorch: `RandomForestClassifier`/
`Regressor` and `HistGradientBoosting*` already cover the "something
stronger than a linear baseline" need without adding a heavyweight
dependency (see `app/ml/__init__.py`'s module map for the full reasoning).

The module is organized around a strict separation that mirrors the rest of
the backend:

- **Dataset suitability** (`suitability.py`) — a purely metadata-driven
  check (no data loading) answering "can this dataset even attempt this
  task," with specific, human-readable rejection reasons (e.g. "Forecasting
  cannot be performed because no datetime column was detected"). This
  drives the frontend's task/dataset picker and independently re-validates
  the exact columns a training request names, before any data is touched.
- **Feature engineering** (`feature_engineering.py`) — sklearn
  `ColumnTransformer`/`Pipeline` builders, always returned *unfitted*.
  Leakage prevention is structural, not a convention to remember: every
  task module calls `.fit()` exactly once, on the training split only, and
  `.transform()` (never refit) on anything held out or predicted later.
- **Per-task modules** (`classification.py`, `forecasting.py`,
  `segmentation.py`, `anomaly_detection.py`) — each trains 2-3 candidate
  models, selects a winner by a metric appropriate to that task (ROC-AUC
  for classification, since accuracy is misleading under class imbalance;
  MAE for forecasting; silhouette score for segmentation), and returns both
  a results payload and a reloadable artifact. Forecasting's splits are
  always chronological — never shuffled — with a genuine backtest (train on
  all-but-the-last-`horizon` periods, score against the real values for
  those periods) kept separate from the unscored production forecast that
  extends past the dataset's real last date.
- **Explainability** (`explainability.py`) — permutation importance
  (`sklearn.inspection`), not SHAP: it works identically regardless of
  whether the underlying model exposes `feature_importances_`/`coef_`,
  which matters because every task compares heterogeneous model types.
  Reported as association ("higher X associated with higher predicted
  probability"), never causation.
- **Orchestration** (`service.py`) — the only module `app/api/ml.py` calls;
  ties dataset lookup, suitability validation, data loading (reusing Phase
  2's ingestion table-reconstruction, not a second ingestion path),
  training, and persistence together.
- **Artifacts** (`artifacts.py`) — joblib files under `Settings.
  ml_artifacts_dir`, one per run, gitignored and never committed. The
  database (`ml_runs` table) stores only metadata and the full results
  payload as JSONB, plus a path to the artifact. Versioning "the same"
  model across runs and a promotion workflow are a separate concern, built
  in Phase 6 as `app/mlops/` (§3.4a) rather than folded in here.

Training is synchronous end-to-end: an API request blocks until the model
is fit. Acceptable at this project's data scale (documented limitation, not
an oversight) — see `backend/README.md`'s Phase 5 section for the specific
numbers. Phase 6 re-evaluated this and explicitly kept it synchronous (see
§3.4a) rather than introducing a job queue speculatively.

### 3.4a MLOps: registry, drift, monitoring (implemented Phase 6)
A native registry and monitoring layer (`backend/app/mlops/`), deliberately
parallel to — not inside — `app/ml/`, since "did this run train correctly"
(Phase 5) and "can this specific version be trusted over time" (Phase 6)
are different questions with different lifecycles.

- **Registry** (`registry_service.py`) — a `ModelVersion` row per
  registered `MLRun`, joined via `ml_run_id` rather than duplicating its
  configuration/results. A forward-only lifecycle (`candidate` → `staging`
  → `production` → `archived`) is enforced in the service layer (each
  transition validated one stage at a time) and, independently, by a
  Postgres partial unique index allowing at most one `production` row per
  (dataset, task type) family — defense in depth against a bug ever
  promoting two conflicting versions live at once. Promoting a new version
  auto-archives the family's previous production version in two sequential
  commits (see `backend/README.md` for why one batched flush is unsafe
  here); archived versions are never deleted, so lineage stays fully
  inspectable.
- **Drift detection** (`drift.py`) — Population Stability Index, the
  standard interpretable drift statistic in production ML systems: PSI
  compares a baseline and current distribution across shared bins
  (quantile bins for numeric features, the union of observed categories for
  categorical ones) and produces one number with conventional thresholds
  (0.10 warning, 0.25 drift), rather than a p-value that still needs a
  separate business decision layered on top. Handles missing values, unseen
  categories, and constant-baseline columns (a dedicated
  `constant_value_deviation` method, since PSI is undefined for a
  one-point distribution) without crashing.
- **Performance monitoring** (`monitoring.py`) — compares a version's
  training-time primary metric against the same metric recomputed on a new
  dataset: ROC-AUC for classification, MAE/RMSE/MAPE for forecasting (both
  genuine ground truth), silhouette score for segmentation, flagged-rate
  for anomaly detection (both unsupervised proxy signals, explicitly marked
  `ground_truth_available: false` rather than presented as equivalent to
  the supervised metrics). Thresholds are direction-aware (higher-is-better
  vs. lower-is-better) and configurable via `Settings`, never hidden inside
  a function body.
- **Monitoring events & alerting** (`service.py`, `MonitoringEvent` model)
  — every drift/performance check writes one event with a normalized
  severity (`info`/`warning`/`critical`), independent of each domain's own
  richer status vocabulary (`stable`/`warning`/`drift`,
  `stable`/`warning`/`degraded`/`not_applicable`), specifically so a future
  alert channel (email/Slack/PagerDuty) can subscribe to "severity ≥
  warning" without knowing which detector produced the event. No such
  channel exists yet — events are queryable via API and rendered on a
  global alerts page and each version's detail page, which is the full
  scope of "alerting" this phase needed.
- **Never auto-remediates.** Detecting drift or degradation only ever
  produces a record; retraining, rollback, or re-promotion stays a
  separate, explicit, human-triggered action through the existing
  train/register/promote endpoints — deliberately, so an automated false
  positive can never retrain or demote a model on its own.

### 3.5 AI platform
- **RAG**: document ingestion → chunking → embeddings (Hugging Face model,
  local by default) → pgvector storage → retrieval → LLM generation with
  citations back to source chunks.
- **LLM provider abstraction**: a single interface behind which a local
  model (e.g. via Ollama/HF) or a hosted API can sit interchangeably,
  selected by environment variable. Default to local/free; hosted APIs are
  opt-in via config, never required to run the project.
- **Knowledge graph** (Phase 9): structured entity/relationship data
  representing enterprise concepts (customers, products, orders, etc.) and
  their connections, queried alongside vector retrieval. Deliberately built
  so it can be *disabled* independently of vector RAG — this toggle is what
  makes the later research comparison (vector-only vs. hybrid) possible.
- **Agents** (Phase 10): narrowly-scoped agents (Data, Analytics, ML,
  Research, Visualization, Decision, Risk) coordinated by an orchestration
  layer, each with a defined tool surface. Built after the primitives they
  orchestrate (ingestion, ML serving, RAG, KG) already exist and work
  standalone — agents compose existing capabilities, they don't replace
  the need to build those capabilities first.

### 3.6 Decision intelligence (Phase 11)
Sits above the ML and AI platforms: turns predictions/retrieved evidence
into recommendations, risk scores, and what-if simulations, with a human
approval workflow before any recommendation is treated as an action.

### 3.7 Security (implemented Phase 4)
JWT-based authentication (`app/auth/`), role-based access control enforced
at the API layer via `Depends(require_permission(...))` (`app/rbac/`), and
an audit log of every security/administration-relevant action
(`app/audit/`). Secrets always via environment variables (`.env`, never
committed — see `.gitignore`), never hard-coded.

Identity and authorization are deliberately separate modules: a JWT proves
*who* (minimal claims - `sub`, `tv`, `iat`, `exp`, nothing else), while
*what they can do* is resolved fresh from the database on every request,
never baked into the token, so a permission change takes effect
immediately rather than waiting for a token to expire. Three roles
(`ADMIN`/`ANALYST`/`VIEWER`, a user may hold more than one) map to a fixed
permission catalog (`dataset:*`, `dashboard:*`, `user:*`, `audit:read`);
revocation (logout, admin deactivation) works via a per-user
`token_version` counter rather than a token blocklist or refresh-token
rotation scheme — simpler, at the accepted cost of invalidating every
session for that user at once rather than just one device. Full rationale,
including the frontend's `localStorage` token-storage tradeoff, is in
`backend/README.md`'s and `frontend/README.md`'s Phase 4 sections.

### 3.8 MLOps & CI/CD
Model registry, drift detection, and performance monitoring are a native
implementation (`backend/app/mlops/`, §3.4a) rather than MLflow or another
external tracker — see §5/§6 for why. GitHub Actions for lint/test/build on
every push. Docker Compose for local multi-container orchestration;
Dockerfiles per service for eventual cloud deployment.

## 4. Data flow (representative example)

1. A CSV is uploaded via the frontend → ingestion endpoint (Data Platform).
2. Schema detection + profiling run; quality score computed; data lands in
   Postgres with lineage metadata recording the source file and transform.
3. BI layer computes KPIs from the now-trusted relational data, rendered as
   dashboards.
4. A churn model (ML Platform), trained earlier and registered/promoted
   through the native model registry, scores the same customer table;
   scores are stored back and surfaced in the dashboard and to the
   Decision layer.
5. A user asks a natural-language question ("why did churn risk increase in
   Q2 for enterprise customers?") → Text-to-SQL + RAG (AI Platform) retrieve
   relevant structured data and supporting documents (with citations) → an
   LLM generates an explanation grounded in both.
6. The Decision layer turns this into a recommendation with a risk score;
   a human approves or rejects it via the approval workflow; the decision
   and its evidence trail are audit-logged.

## 5. Technology choices and rationale

| Choice | Rationale |
|---|---|
| **PostgreSQL + pgvector** over a dedicated vector DB | One system to run, back up, and reason about locally. pgvector is sufficient at portfolio data volumes and keeps relational + vector data joinable in a single query — which directly matters for the RAG-vs-hybrid-KG research comparison. |
| **FastAPI** over Flask/Django | Async support, Pydantic-native validation, automatic OpenAPI docs that double as the frontend's API contract. |
| **Native model registry** over MLflow (decided Phase 6) | The platform only needs to track its own `MLRun`s, not arbitrary third-party experiments — a `ModelVersion` table joined to the existing `ml_runs` table covers every field the registry needs (config, metrics, dataset, seed, lineage) with zero new infrastructure to run, secure, or back up. Revisit only if a future phase needs cross-tool experiment tracking MLflow specializes in. |
| **Population Stability Index** for drift over a statistical hypothesis test | PSI produces one interpretable number with conventional thresholds and degrades gracefully with missing values/small samples; a KS-test/chi-squared test would give a p-value that still needs a separate, undocumented business decision on top to become an actionable "is this drift." |
| **Monolithic backend with domain modules** over microservices | No independent scaling/deploy need yet; microservices would add distributed-systems complexity that teaches infrastructure lessons unrelated to this project's actual learning goals. |
| **Configurable LLM provider, local-first** over a single paid API | Keeps the project runnable at zero cost; demonstrates provider-abstraction as a real engineering concern; avoids a hard dependency on any one vendor. |
| **GitHub Actions** over other CI | Free for public/private repos at this scale, integrates directly with GitHub hosting. |
| **Docker Compose** over Kubernetes | Compose is sufficient for "run everything locally"; Kubernetes solves cluster-orchestration problems this project doesn't have. |

## 6. What is deliberately NOT used (yet)

| Technology | Why it's excluded now | When it might be reconsidered |
|---|---|---|
| **Kafka / message brokers** | No streaming/multi-consumer need yet; batch ingestion is sufficient through at least Phase 8. | Only if a genuine event-driven use case emerges (e.g. real-time ingestion demo). |
| **Spark** | Data volumes at portfolio scale fit comfortably in Pandas/Postgres. Spark solves a scale problem this project doesn't have. | Not planned; would need a specific large-data justification. |
| **Kubernetes** | Docker Compose covers local dev; a single-container-per-service AWS deployment (Phase 13) doesn't need cluster orchestration. | Only if cloud deployment specifically requires it — not the current plan. |
| **Neo4j (or other graph DB)** | The knowledge graph (Phase 9) will first be attempted as relational tables in Postgres (entities/relationships as rows) to avoid a second database. | Revisit in Phase 9 if graph traversal queries prove awkward in SQL. |
| **Paid LLM APIs by default** | Violates the near-zero-cost constraint; local models (via Hugging Face/Ollama) are the default. | Paid APIs remain available as an *opt-in* configured provider, never a requirement. |
| **A second database engine** | PostgreSQL + pgvector covers relational and vector needs together. | Only if a specific workload (e.g. very large-scale vector search) outgrows pgvector. |
| **Celery / task queues** | No long-running async job need yet; FastAPI's background tasks or synchronous processing suffice through early phases, including Phase 6's drift/performance checks. | Revisit if ingestion, model training, or monitoring checks need true background job queuing with retries at larger data scale. |
| **Separate microservices per platform (Data/ML/AI)** | Would add deployment/networking complexity before there's a scaling reason to. | Revisit only with a concrete independent-scaling or independent-deploy justification. |
| **MLflow (or another external experiment tracker/registry)** | Phase 6's registry only needs to version this platform's own training runs, not arbitrary experiments from other tools; a native `ModelVersion` table reusing the existing `ml_runs` data covers the full spec with no new service to run. | Revisit only if a future phase needs cross-tool experiment comparison or a team-facing tracking UI beyond this platform's own frontend. |
| **Auto-remediation on drift/degradation** | Phase 6 deliberately only ever *records* a drift or performance event; retraining/rollback/promotion stays a separate, explicit, human-triggered action. | Not currently planned — an automated actor retraining or demoting a production model on an unreviewed signal is a risk this project chooses not to take on. |

## 7. Open questions (to resolve in later phases, not now)

- Knowledge graph storage: relational-tables-in-Postgres vs. a graph
  library vs. (last resort) a dedicated graph DB — decide in Phase 9.
- Agent orchestration framework: hand-rolled vs. a library (e.g.
  LangGraph) — decide in Phase 10 once the agents' actual coordination
  needs are concrete.

*(Resolved: the model registry backend-store question this section
originally listed for Phase 1 was answered in Phase 6 — no MLflow, no
separate store; see §3.4a, §5, §6.)*

These are explicitly deferred, not accidentally omitted.
