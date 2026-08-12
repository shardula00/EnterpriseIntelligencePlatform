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

**Implementation notes (decided during Phase 2, not in the original plan):**
- **One physical table per upload**, dynamically created in a dedicated
  `ingested` Postgres schema (table name derived from the dataset's UUID).
  Metadata about every dataset (schema, profile, quality issues, lineage)
  lives in four generic tables in `public` — nothing in the schema itself
  ever names a specific business concept.
- **Identifier safety over trust**: raw headers are forced through an
  allow-list sanitizer (`[a-z0-9_]` only) before anything reaches SQL, and
  tables are built via SQLAlchemy `Table`/`Column` objects rather than
  string-built DDL. Verified with a dedicated SQL-injection-attempt test.
- **Quality score computed before the Postgres write, not after** — the
  physical table, its quality report, and its lineage record are written
  together in one transaction, so nothing is ever left half-created.
- **Profiling runs after type coercion**, not before — computing a mean or
  min/max on still-raw text would either crash or be meaningless.
- Re-uploading a file creates an independent new dataset; there is no
  versioning/append-to-existing-dataset concept yet (a reasonable future
  extension, out of scope for Phase 2).

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

**Implementation notes (decided during Phase 3, not in the original plan):**
- **KPI "definitions" are derived from column metadata, not hand-picked
  per business domain**: every numeric column gets sum/average/min/max
  tiles; every low-cardinality text/boolean column becomes a breakdown
  candidate; every datetime column becomes a trend candidate. A candidate
  must also group *multiple* rows on average (distinct_count roughly
  ≤ row_count/2) - a column with one distinct value per row (e.g. a name
  column) clears a naive cardinality cap but produces a meaningless
  "breakdown," so that's excluded even though it's technically low enough
  cardinality on an absolute scale.
- **No new database schema.** KPIs are computed live via SQL against a
  dataset's existing physical table (reusing `ingestion.table_builder`);
  nothing new is persisted.
- **CORS added to the backend** (`Settings.cors_allow_origins`, allow-listed
  local dev origins only) - the one backend change made purely to support
  the frontend, not a new feature in its own right.
- **Typed API client generated from the real OpenAPI schema**
  (`openapi-typescript` + `openapi-fetch`), regenerated via
  `npm run generate:api` whenever backend routes/models change - not
  hand-maintained types that can silently drift from what the API returns.
- Two frontend dependencies beyond the plan's named stack, both narrowly
  justified: `react-router-dom` (multi-screen navigation) and `recharts`
  (the "interactive charts" the plan calls for). No data-fetching/caching
  library (e.g. React Query) - a small custom hook (`useAsync`) covers
  loading/success/error state at this scale.
- End-to-end verified with a real headless-browser walkthrough (upload →
  list → all five detail tabs) against the live backend, not just API
  curl calls and mocked component tests - see the Phase 3 completion
  report for what was checked.

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

**Implementation notes (decided during Phase 4, not in the original plan):**
- **Three separate backend concerns, three packages**: `app/auth/`
  (identity - registration, login, password hashing, JWT), `app/rbac/`
  (authorization - roles, permissions, `require_permission(...)`), `app/audit/`
  (event recording/querying). Identity and authorization are deliberately
  decoupled: a JWT only proves *who*, never *what they can do* - permissions
  are re-resolved from the database on every request via
  `rbac.service.effective_permissions()`, never cached in the token.
- **JWT claims are minimal by design**: `sub` (user id), `tv` (token
  version), `iat`, `exp` - no email, name, roles, or permissions. Two
  reasons: a JWT is base64, not encrypted, so anything in it is readable by
  whoever holds it; and roles/permissions can change between issuance and
  use, so baking them in would let a revoked permission keep working until
  natural expiry.
- **No refresh tokens.** A single 60-minute access token, and revocation is
  via `User.token_version`: logout and admin-deactivation both increment it,
  and `get_current_user` rejects any token whose `tv` claim doesn't match
  the user's current value. Tradeoff accepted: this invalidates *every*
  active session for that user, not just the one that logged out - judged
  an acceptable simplicity/security tradeoff at this scale, not something a
  multi-device product would want.
- **Self-privilege-escalation is blocked by a blanket rule, not a
  case-by-case check**: an admin cannot change their own role assignment or
  active status via the admin API at all (not "cannot increase" - cannot
  change), which is simpler to reason about and impossible to get wrong at
  the boundary.
- **Registration always grants VIEWER**, never anything higher - the only
  way to get ANALYST/ADMIN is an existing admin granting it. This is what
  makes open self-registration safe to leave on.
- **Login failure messages never distinguish "wrong password" from
  "no such email"** (same exception, same HTTP response) - the standard
  account-enumeration mitigation. Registration *does* say "email already
  exists," which is normal and expected at signup (the alternative is a
  broken-feeling signup form) and not treated as the same enumeration risk.
- **Frontend token storage: localStorage, not an httpOnly cookie** -
  documented as a deliberate portfolio-scale tradeoff (XSS-exposed, but
  short-lived, no refresh token, no HTML rendered from user input anywhere
  in the app) rather than building cookie+CSRF machinery this phase. See
  `frontend/src/auth/tokenStorage.ts` and `frontend/README.md`.
- **Backend authorization is what's tested for 401/403, not frontend
  hiding** - every RBAC test hits the real HTTP API directly; the frontend's
  `usePermission()`-based hiding (delete buttons, admin nav links,
  dashboard-configure controls) is UX only and is explicitly verified in
  the E2E pass to be backed by an independent server-side rejection, not a
  substitute for one.
- Existing Phase 2/3 tests needed zero content changes: the `client` test
  fixture became admin-authenticated by default (see `tests/conftest.py`),
  so every pre-Phase-4 integration test kept working unmodified while new,
  dedicated tests in `tests/auth/`, `tests/rbac/`, `tests/audit/` cover the
  permission boundaries themselves.

---

## Phase 5 — Classical Machine Learning ✅ complete

**Objective:** Real predictive models, evaluated and served properly, not
notebook-only experiments.

**Deliverables (as actually built — see implementation notes below for why
this differs from the original plan):**
- Generic, per-task dataset suitability checking (not hardcoded to one
  dataset) with specific human-readable rejection reasons
- Binary classification (e.g. churn), time-series forecasting, customer
  segmentation, anomaly detection — each with 2-3 candidate models compared
  on a task-appropriate metric, leakage-safe preprocessing, and
  explainability via permutation importance
- API endpoints: suitability, train (one per task), run history/results,
  predict — gated by new `ml:read`/`ml:train`/`ml:predict` permissions
  added through the existing RBAC seed mechanism
- `ml_runs` table (metadata + full results as JSONB) via Alembic; model
  artifacts stored locally as joblib files, versioned by run, never
  committed
- Frontend `/ml` section: task selection, dataset suitability, per-task
  configuration, training, model comparison, metrics, predictions, feature
  importance, per-task visualizations
- 4 new synthetic fixture datasets (one purpose-built per task) plus 79
  new backend tests and 46 new frontend tests
- Tests: suitability edge cases, leakage-prevention checks, one test module
  per task, full API/permission coverage; real 4-task browser E2E (0
  console/page/network errors)

**Definition of done:** Each task can be trained via the API/UI on a
suitable dataset, results and metrics are real (not mocked), predictions
are servable from a persisted artifact, and the full existing (Phase 1–4)
test suite still passes unmodified in intent (2 pre-existing RBAC tests
were updated to reflect the new permission catalog, not to work around a
bug).

**Implementation notes (decided during Phase 5, not in the original plan):**
- **No MLflow, no model registry, no monitoring/drift detection — moved to
  Phase 6.** The original plan bundled experiment tracking and a model
  registry into this phase; on reflection, a full registry (versioning "the
  same" model across retrains, promotion workflows) is a distinct MLOps
  concern from "can the platform train and evaluate a model correctly,"
  and pulling it forward would have meant building registry machinery
  before there's more than one candidate registry entry to manage. What
  Phase 5 persists instead is exactly what's needed for reproducibility
  today: per-run metadata (dataset, task, config, seed, timestamp) and
  results in `ml_runs`, plus the artifact on disk — explicitly documented
  in `app/ml/artifacts.py` and `app/models/ml_run.py` as *not* a registry.
- **No XGBoost.** `RandomForestClassifier`/`Regressor` and
  `HistGradientBoosting*` (both in scikit-learn already) cover the
  "something stronger than a linear/naive baseline" need for all 4 tasks
  without adding a second heavyweight ML dependency. See
  `backend/app/ml/__init__.py`.
- **No SHAP.** `sklearn.inspection.permutation_importance` gives
  model-agnostic feature importance that works identically across every
  candidate model type (linear, random forest, gradient boosting) each task
  compares — SHAP would need model-specific explainers and add a
  dependency for a marginal accuracy gain in explanation fidelity that
  isn't needed at this scale.
- **Reused Phase 2's ingestion table-reconstruction, not a second data path.**
  `app/ml/data_loading.py` loads a dataset's physical table the same way
  `app/ingestion/service.get_preview` does, via `table_builder.
  build_dataset_table` + `fetch_preview_rows`. This surfaced a real,
  pre-existing (Phase 2) bug: `fetch_preview_rows` returns row dict keys as
  SQLAlchemy `quoted_name` (a `str` subclass), invisible to every existing
  caller (they only ever serialize to JSON) but silently breaking
  scikit-learn's strict `type(name) is str` column-name detection deep
  inside `ColumnTransformer`. Fixed with a one-line `str(k)` cast in
  `data_loading.py` — scoped to the ML loader, since that's the only
  caller that needed it.
- **Forecasting is never downsampled**, unlike the other 3 tasks (capped
  at `Settings.ml_max_training_rows`, default 50,000, with `was_sampled`
  recorded in the run). A time series' row *order* is the signal; a random
  sample would destroy the chronological sequence lags and backtesting
  depend on.
- **Training is synchronous end-to-end** — an API request blocks until the
  model is fit. Acceptable at this project's data scale (largest fixture:
  505 rows; full run including all 3 RandomForest/HistGB candidates
  typically completes in well under a second once warmed up). Documented
  as a limitation for Phase 6 to address with async job execution if
  dataset sizes grow, not silently deferred.
- **`MLRunResultsOut.results` is a real Pydantic union**
  (`ClassificationResultsOut | ForecastResultsOut | SegmentationResultsOut |
  AnomalyResultsOut`), not `dict[str, Any]`, even though the underlying
  `ml_runs.results` database column is a single JSONB field whose shape
  genuinely differs per task. Re-validating the stored dict against the
  union on the way out means the OpenAPI schema — and so the
  `openapi-typescript`-generated frontend types — describes all 4 real
  result shapes instead of an opaque blob, which is what let the frontend
  render real, typed results instead of stringly-typed lookups.
- **Frontend results-view union narrowing uses the run's own `task_type`**,
  not a discriminator field on the result types themselves (none of the 4
  result schemas carry one) — `isClassificationResults()` /
  `isForecastResults()` / etc. in `frontend/src/api/types.ts` narrow on the
  sibling `run.task_type` field instead, documented inline as the reason
  they exist rather than a discriminated union.
- Existing Phase 1–4 tests needed only two intentional content updates, not
  workarounds: `tests/rbac/test_service.py` and `tests/rbac/test_api.py`'s
  hardcoded VIEWER/ANALYST permission sets and the "10 permissions" catalog
  count were updated to include the 3 new `ml:*` permissions — a correct
  consequence of extending the catalog, verified by reading the actual
  diff, not a bug being paved over.

---

## Phase 6 — MLOps Hardening ✅ complete

**Objective:** Move from "a model that works once" to "a model system that
can be trusted over time."

**Deliverables (as actually built — see implementation notes below for why
this differs from the original plan):**
- A native `ModelVersion` registry (`app/models/model_version.py`) —
  every completed `MLRun` can be registered as a version, preserving full
  lineage (dataset → config/results via `ml_run_id` → artifact checksum →
  version → lifecycle state) without duplicating anything `MLRun` already
  stores
- A forward-only lifecycle state machine — candidate → staging →
  production → archived — enforced both in the service layer and by a
  Postgres partial unique index guaranteeing at most one `production`
  version per (dataset, task type) family; promoting a new version
  auto-archives the family's previous production version, and history for
  both remains fully inspectable
- Data drift detection (`app/mlops/drift.py`) via Population Stability
  Index — quantile-binned for numeric features, category-union-based for
  categorical — with published, documented thresholds (0.10 warning, 0.25
  drift) and a dedicated code path for constant-baseline columns, where PSI
  is mathematically undefined
- Model performance monitoring (`app/mlops/monitoring.py`) per task type —
  real ground-truth metrics for classification (ROC-AUC) and forecasting
  (MAE/RMSE/MAPE), explicitly-labeled unsupervised proxy signals for
  segmentation (silhouette) and anomaly detection (flagged-rate) — with a
  `ground_truth_available` flag surfaced through the API and UI rather than
  papering over the difference
- An internal `MonitoringEvent` log recording every drift/performance
  check with a normalized severity (info/warning/critical), queryable via
  API and rendered as a global alerts page and per-version history — built
  so a future email/Slack/cloud channel can subscribe to it without
  touching the detection engine
- 8 new REST endpoints (register/list/detail/promote/archive/drift-check/
  performance-check/monitoring-events) gated by 3 new RBAC permissions
  (`mlops:read`, `mlops:evaluate`, `mlops:promote`) added through the
  existing seed mechanism, every lifecycle/check action dual-written to the
  audit log
- Frontend `/mlops` section extending the existing ML UI (not a second
  design system): Model Registry list, Model Version Detail (reusing
  Phase 5's exact per-task results components), Drift Monitoring panel,
  Performance Monitoring panel, and a global Monitoring Alerts page
- 4 new synthetic monitoring fixtures (stable / moderate drift / severe
  drift / degraded performance) plus 49 new backend tests and 28 new/updated
  frontend tests
- Async training execution was evaluated and explicitly **not** built —
  see implementation notes

**Definition of done:** Feeding the system a deliberately shifted dataset
triggers a detectable drift signal, visible via API and frontend, and
recorded as an auditable event — verified with a real browser walkthrough:
train → register → promote candidate → staging → production → run a drift
check against a shifted dataset → drift detected → run a performance check
against a degraded dataset → degradation detected → both visible on the
version detail page and the global alerts page, 0 console/page/network
errors. A second model version trained on the same dataset/task family
correctly becomes the new production version while the first is
auto-archived and remains fully inspectable (verified by test and by the
registry API). The full pre-Phase-6 backend and frontend suites, and all
four Phase 5 ML workflows, were re-verified end-to-end and pass unmodified
in intent.

**Implementation notes (decided during Phase 6, not in the original plan):**
- **No MLflow.** A registry that only needs to track *this platform's own*
  `MLRun`s — not arbitrary third-party experiments, not distributed
  training, not a UI of its own — doesn't need an external experiment-
  tracking server. A single `ModelVersion` table joined to the existing
  `ml_runs` table via `ml_run_id` covers every piece of metadata the spec
  asked for (config, metrics, dataset, seed, timestamps) with zero
  duplication and zero new infrastructure to run/secure/back up.
- **No Celery/Redis.** Drift checks and performance checks run against
  fixture-scale datasets (hundreds to low thousands of rows) inside a
  single synchronous request, consistent with Phase 5's decision on
  training itself. Documented as a limitation for a future phase to revisit
  if dataset sizes grow — not silently deferred.
- **`ModelVersion` never duplicates `MLRun.configuration`/`results`.** The
  detail API joins them via `ml_run_id`; the frontend's
  `ModelVersionDetailPage` reuses Phase 5's exact
  `ClassificationResultsView`/`ForecastResultsView`/`SegmentationResultsView`/
  `AnomalyResultsView` components rather than re-rendering metrics from
  scratch — the same visual language, not a second one.
- **PSI (Population Stability Index), not a statistical hypothesis test.**
  PSI is the standard, widely-published drift metric in production ML
  systems specifically because it's interpretable as a single number with
  conventional thresholds, doesn't require distributional assumptions, and
  degrades gracefully with missing values/unseen categories/small samples —
  a KS-test or chi-squared test would give a p-value that's harder to turn
  into an actionable "is this drift" decision at arbitrary sample sizes.
- **A dedicated `constant_value_deviation` method for constant-baseline
  columns.** PSI divides by each bin's baseline proportion; a column with
  a single distinct value in the baseline has one bin holding 100% of the
  mass, making PSI either undefined or meaningless the moment any new value
  appears. Detected explicitly and reported as "the fraction of new rows
  that differ from the constant baseline value," never silently producing
  a `0.0`/"stable" false negative.
- **`ground_truth_available: bool` is a first-class field, not an
  afterthought.** Segmentation's silhouette score and anomaly detection's
  flagged-rate are real, useful signals, but neither is "accuracy against a
  known correct answer" the way classification/forecasting are — the field
  (and a distinct UI badge) says so honestly instead of presenting all four
  task types' numbers as the same kind of measurement.
- **Two sequential commits on promote-to-production, not one batched
  flush.** Auto-archiving the previous production version and promoting the
  new one are two ORM updates in the same request; SQLAlchemy can submit
  them as one batched multi-row `UPDATE`, and Postgres evaluates the
  family's partial unique index mid-batch — occasionally raising a spurious
  `IntegrityError` depending on statement ordering. Splitting into two
  `db.commit()` calls (archive-and-commit, then promote-and-commit) avoids
  the race; Postgres cannot make a partial unique index `DEFERRABLE` (only
  full constraints support that), so this had to be fixed at the
  transaction-shape level, not with a deferred-constraint flag.
- **Drift/performance checks notify their parent page via an `onChecked`
  callback.** Caught by the real browser E2E, not a unit test: the model
  version detail page's "monitoring history" section fetches once on
  mount and has no reason to know a check just ran in a sibling panel.
  Without an explicit callback, a newly-recorded event was invisible on
  the same page until a manual reload — fixed by having
  `DriftCheckPanel`/`PerformanceCheckPanel` call an optional `onChecked`
  prop on success, wired to the history list's own `reload()`.
- Existing Phase 0–5 tests needed only the same kind of intentional catalog
  update Phase 4 and 5 each required: `tests/rbac/test_api.py` and
  `tests/rbac/test_service.py`'s hardcoded permission-count/VIEWER/ANALYST
  assertions were updated to include the 3 new `mlops:*` permissions.

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
