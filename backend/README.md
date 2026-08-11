# backend/

FastAPI backend for the Enterprise Intelligence Platform. Phase 1 added the
foundational plumbing (settings, DB connection, migrations, health check).
Phase 2 added generic dataset ingestion (CSV/Excel/JSON upload -> schema
detection -> profiling -> quality scoring -> a real Postgres table ->
lineage). Phase 3 added a generic KPI engine (`app/bi/`) and CORS support
for the new React frontend. Phase 4 added authentication, RBAC, and audit
logging (`app/auth/`, `app/rbac/`, `app/audit/`) - every dataset/KPI/user/
audit route now requires a valid JWT and the right permission. Phase 5 added
classical ML (`app/ml/`) - dataset suitability checking, leakage-safe
training/evaluation for 4 tasks (classification, forecasting, segmentation,
anomaly detection), and prediction serving from persisted artifacts. Further
domain features (RAG, MLOps hardening, etc.) arrive in later phases per
[DEVELOPMENT_PLAN.md](../DEVELOPMENT_PLAN.md).

## Prerequisites

- Python 3.12 (`.python-version` at the repo root pins this)
- Docker Desktop (for Postgres via `infra/docker-compose.yml`)

## First-time setup

```powershell
# 1. Start Postgres (from infra/)
cd ../infra
cp .env.example .env
docker compose up -d

# 2. Set up the backend virtual environment (from backend/)
cd ../backend
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

# 3. Configure the app
cp .env.example .env
# .env's DATABASE_URL must match infra/.env's credentials/port - the
# defaults in both .env.example files already match each other.

# 4. Apply database migrations
.venv\Scripts\alembic upgrade head

# 5. Bootstrap the first admin account (Phase 4) - see "Authentication &
#    RBAC" below for the full explanation. Set a real password via env var,
#    never hard-code one:
$env:BOOTSTRAP_ADMIN_EMAIL = "admin@example.com"
$env:BOOTSTRAP_ADMIN_PASSWORD = "choose-a-real-local-dev-password"
.venv\Scripts\python.exe -m scripts.bootstrap_admin
```

If you're using VS Code, point its Python interpreter at
`backend/.venv/Scripts/python.exe` (Ctrl+Shift+P -> "Python: Select
Interpreter") so imports resolve correctly in the editor.

## Running the app

```powershell
.venv\Scripts\uvicorn app.main:app --reload
```

Then visit `http://localhost:8000/health` - it should report
`"status": "ok"` and `"database": "connected"`. Interactive API docs (from
FastAPI's auto-generated OpenAPI schema) are at `http://localhost:8000/docs`.

## Running tests

Tests run against the same Postgres started above (the health check is
read-only, so this is safe):

```powershell
.venv\Scripts\pytest -v
```

## Linting

```powershell
.venv\Scripts\ruff check .
```

CI (`.github/workflows/backend-ci.yml`) runs this same lint step, plus
migrations and tests, against a freshly started `pgvector/pgvector:pg16`
container on every push/PR touching `backend/`.

## Database migrations

Migrations live in `migrations/versions/`, managed by Alembic. The
connection string comes from `Settings.database_url` (see `app/config.py`),
not from `alembic.ini` directly - see the comment in `alembic.ini` for why.

```powershell
# After changing a model in app/models/:
.venv\Scripts\alembic revision --autogenerate -m "describe the change"
# Review the generated file in migrations/versions/ before applying -
# autogenerate does not detect everything (e.g. it missed the pgvector
# CREATE EXTENSION statement in the first migration; that was added by hand).
.venv\Scripts\alembic upgrade head
```

## Dataset ingestion (Phase 2)

Upload a CSV, XLSX, or JSON file and the pipeline will: sanitize headers
into safe Postgres identifiers, detect each column's type, coerce/clean the
data, profile it, score its quality, load it into a real table in the
`ingested` schema, and record every step as a lineage event. Nothing about
this is specific to any one business schema - it works the same way for
any flat tabular file. See [ARCHITECTURE.md](../ARCHITECTURE.md) or the
module docstrings under `app/ingestion/` for the full design rationale.

All of these now require authentication (Phase 4) - get a token first:

```powershell
$body = @{ email = "admin@example.com"; password = "choose-a-real-local-dev-password" } | ConvertTo-Json
$token = (Invoke-RestMethod -Uri http://localhost:8000/auth/login -Method Post -Body $body -ContentType "application/json").access_token
$headers = @{ Authorization = "Bearer $token" }

# Upload one of the committed test fixtures as a quick demo:
curl -X POST http://localhost:8000/datasets/upload -H "Authorization: Bearer $token" -F "file=@tests/fixtures/orders_sample.csv"

# Then, with the returned "id":
curl http://localhost:8000/datasets/<id> -H "Authorization: Bearer $token"
curl http://localhost:8000/datasets/<id>/columns -H "Authorization: Bearer $token"
curl http://localhost:8000/datasets/<id>/quality -H "Authorization: Bearer $token"
curl http://localhost:8000/datasets/<id>/lineage -H "Authorization: Bearer $token"
curl "http://localhost:8000/datasets/<id>/preview?limit=10" -H "Authorization: Bearer $token"
curl -X DELETE http://localhost:8000/datasets/<id> -H "Authorization: Bearer $token"  # requires dataset:delete (ADMIN)
```

Endpoints: `POST /datasets/upload` (needs `dataset:create`), `GET /datasets`,
`GET /datasets/{id}`, `GET /datasets/{id}/columns`,
`GET /datasets/{id}/quality`, `GET /datasets/{id}/lineage`,
`GET /datasets/{id}/preview` (all need `dataset:read`),
`DELETE /datasets/{id}` (needs `dataset:delete`, ADMIN-only by default).

Uploaded files are retained for provenance under
`Settings.upload_storage_dir` (defaults to `<repo-root>/data/raw/uploads`,
gitignored - never committed). Test fixtures live in `tests/fixtures/` and
*are* committed - they're small, synthetic, and needed for the test suite
to run from a fresh clone.

## KPI engine (Phase 3)

Every numeric column in a dataset automatically gets sum/average/min/max
stat tiles; every low-cardinality text/boolean column becomes a candidate
breakdown dimension; every datetime column becomes a candidate trend axis.
Nothing here is specific to a business schema - "revenue," "churn," etc.
are never referenced, only column *types* and *cardinality* detected in
Phase 2. See `app/bi/service.py`'s module docstring for the full rationale.

```powershell
curl http://localhost:8000/datasets/<id>/kpis -H "Authorization: Bearer $token"                        # dashboard:read
curl "http://localhost:8000/datasets/<id>/kpis/breakdown?group_by=category&metric=quantity&agg=sum" -H "Authorization: Bearer $token"  # dashboard:configure
curl "http://localhost:8000/datasets/<id>/kpis/trend?date_column=order_date&metric=quantity&granularity=month&agg=sum" -H "Authorization: Bearer $token"  # dashboard:configure
```

## Authentication & RBAC (Phase 4)

Every route except `GET /health`, `POST /auth/register`, and
`POST /auth/login` requires a valid `Authorization: Bearer <token>` header.
See `app/auth/`, `app/rbac/`, `app/audit/` module docstrings for the full
design rationale; summary:

- **Identity vs. authorization are separate.** A JWT only proves *who*
  (`sub`, `tv`, `iat`, `exp` claims - nothing else, see
  `app/auth/security.py`); *what they can do* is resolved fresh from the
  database on every request via `rbac.service.effective_permissions()`,
  never cached in the token.
- **Roles**: `ADMIN`, `ANALYST`, `VIEWER` - a user can hold more than one;
  effective permissions are the union across all assigned roles.
- **Permissions**: `dataset:read/create/delete`, `dashboard:read/configure`,
  `user:read/create/update/delete`, `audit:read`. Default grants (see
  `app/rbac/seed.py`): VIEWER gets read-only dataset/dashboard access;
  ANALYST adds dataset upload and dashboard configuration; ADMIN gets
  everything, including `dataset:delete` (deliberately not given to
  ANALYST) and all `user:*`/`audit:*` permissions.
- **Routes are gated with `Depends(require_permission("..."))`**
  (`app/rbac/dependencies.py`) at the route definition - not scattered
  `if role == ...` checks in handlers.
- **Self-privilege-escalation is blocked categorically**: nobody can change
  their own role assignment or active status via the admin API, at all.
- **Registration always grants VIEWER.** The only way to get ANALYST/ADMIN
  is an existing admin granting it via `POST /users/{id}/roles`.
- **No refresh tokens.** One 60-minute access token; logout and admin
  deactivation both bump `User.token_version`, and any token whose `tv`
  claim no longer matches is rejected - this invalidates every active
  session for that user at once, not just one device/browser.

```powershell
curl -X POST http://localhost:8000/auth/register -H "Content-Type: application/json" `
  -d '{"email":"analyst@example.com","password":"Password123","full_name":"A Analyst"}'
curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" `
  -d '{"email":"analyst@example.com","password":"Password123"}'
curl http://localhost:8000/auth/me -H "Authorization: Bearer $token"
curl -X POST http://localhost:8000/auth/logout -H "Authorization: Bearer $token"

# Admin user management (needs user:read/create/update/delete):
curl http://localhost:8000/users -H "Authorization: Bearer $token"
curl -X POST http://localhost:8000/users/<id>/roles -H "Authorization: Bearer $token" `
  -H "Content-Type: application/json" -d '{"role_names":["ANALYST"]}'
curl -X PATCH http://localhost:8000/users/<id> -H "Authorization: Bearer $token" `
  -H "Content-Type: application/json" -d '{"is_active":false}'
curl http://localhost:8000/roles -H "Authorization: Bearer $token"
curl http://localhost:8000/permissions -H "Authorization: Bearer $token"
```

### Bootstrap admin

`scripts/bootstrap_admin.py` seeds the roles/permissions catalog and
creates the first admin account - idempotent, safe to re-run. It reads
`BOOTSTRAP_ADMIN_EMAIL`/`BOOTSTRAP_ADMIN_PASSWORD` from the environment and
refuses to run if the password isn't set (no hard-coded fallback). See the
"First-time setup" section above for the exact command.

## Audit logging (Phase 4)

`app/audit/service.py`'s `record_event(...)` is the single place any audit
row is ever written - registration, login (success and failure), logout,
dataset upload/deletion, and every admin user-management action all go
through it, which is also where a fixed set of forbidden metadata keys
(`password`, `token`, `secret`, etc., case-insensitive) is stripped before
the row is written, regardless of what a caller passed in.

```powershell
curl "http://localhost:8000/audit-logs?limit=20&action=dataset.deleted" -H "Authorization: Bearer $token"  # needs audit:read
```

## Classical ML (Phase 5)

Four tasks, generically over any suitable uploaded dataset (never hardcoded
to a specific business schema): binary classification, time-series
forecasting, customer segmentation, anomaly detection. See
`app/ml/__init__.py`'s module map and `ARCHITECTURE.md` §3.4 for the full
design rationale; summary:

- **Suitability first.** `GET /datasets/{id}/ml/suitability` reports, for
  all 4 tasks at once, whether the dataset qualifies and - if not - exactly
  why (e.g. "Forecasting cannot be performed because no datetime column was
  detected"), plus suggested columns for whichever tasks *are* suitable.
  This is metadata-only (no data loading), so it's cheap to call for every
  dataset up front.
- **Leakage prevention is structural.** Every task's preprocessing is an
  sklearn `Pipeline`/`ColumnTransformer`, fit exactly once on the training
  split; the test split and any later prediction data only ever go through
  `.transform()`. Forecasting's train/test split is always chronological -
  never shuffled - with the shown metrics coming from a genuine backtest
  (score the model against real held-out periods) kept separate from the
  unscored production forecast that extends past the last real date.
- **Model selection is metric-appropriate, not just highest-accuracy.**
  ROC-AUC for classification (churn-shaped problems are usually imbalanced),
  MAE for forecasting, silhouette score for segmentation. See each task
  module's `PRIMARY_METRIC`/`PRIMARY_METRIC_RATIONALE`.
- **Explainability via permutation importance**, not SHAP - works
  identically across every candidate model type, and is always phrased as
  association ("higher X associated with higher predicted probability"),
  never causation.
- **No model registry.** `ml_runs` stores per-run metadata and the full
  results payload (JSONB); the fitted model itself is a joblib file under
  `Settings.ml_artifacts_dir` (gitignored). There is no versioning of "the
  same" model across retrains and no promotion workflow - that's Phase 6.
- **Training is synchronous** - an API request blocks until the model is
  fit. Fine at this project's data scale (see `Settings.
  ml_max_training_rows`, default 50,000 - forecasting is exempt from
  downsampling since row order is the signal); flagged for Phase 6 to
  revisit with async job execution if that changes.

```powershell
# Suitability (needs ml:read):
curl http://localhost:8000/datasets/<id>/ml/suitability -H "Authorization: Bearer $token"

# Train (needs ml:train) - one endpoint per task:
curl -X POST http://localhost:8000/ml/train/classification -H "Authorization: Bearer $token" `
  -H "Content-Type: application/json" -d '{"dataset_id":"<id>","target_column":"churned"}'
curl -X POST http://localhost:8000/ml/train/forecasting -H "Authorization: Bearer $token" `
  -H "Content-Type: application/json" -d '{"dataset_id":"<id>","datetime_column":"order_date","target_column":"sales_amount","horizon":14}'
curl -X POST http://localhost:8000/ml/train/segmentation -H "Authorization: Bearer $token" `
  -H "Content-Type: application/json" -d '{"dataset_id":"<id>","n_clusters":4}'
curl -X POST http://localhost:8000/ml/train/anomaly-detection -H "Authorization: Bearer $token" `
  -H "Content-Type: application/json" -d '{"dataset_id":"<id>","contamination":0.05}'

# Run history/results (needs ml:read), predict from a trained run (needs ml:predict):
curl http://localhost:8000/ml/runs -H "Authorization: Bearer $token"
curl http://localhost:8000/ml/runs/<run_id> -H "Authorization: Bearer $token"
curl -X POST http://localhost:8000/ml/runs/<run_id>/predict -H "Authorization: Bearer $token" `
  -H "Content-Type: application/json" -d '{}'
```

Permissions (see `app/rbac/seed.py`): `ml:read` (VIEWER and up), `ml:train`
and `ml:predict` (ANALYST and up). New synthetic fixture datasets for
exercising all 4 tasks (never a modification of the existing Phase 2
fixtures) live in `tests/fixtures/ml_*.csv` - `ml_churn_sample.csv`
(classification), `ml_sales_timeseries_sample.csv` (forecasting),
`ml_customers_segmentation_sample.csv` (segmentation),
`ml_transactions_anomaly_sample.csv` (anomaly detection).

## CORS (Phase 3)

The React dev server (`http://localhost:5173`) runs on a different origin
than the API, so `Settings.cors_allow_origins` (see `.env.example`)
explicitly allow-lists it in `app/main.py`. Add any other frontend origins
there if needed - never widen this to a wildcard.

## Layout

```
app/
  main.py       - FastAPI app + router registration + CORS
  config.py     - Pydantic Settings, loaded from environment/.env
  db.py         - SQLAlchemy engine, session factory, declarative Base
  models/       - ORM models (import every model in models/__init__.py so
                  Alembic autogenerate can see it)
  api/          - API routers, one module per concern
  ingestion/    - dataset ingestion pipeline (parsing, type inference,
                  profiling, quality scoring, dynamic table creation,
                  orchestration) - see module docstrings for details
  bi/           - generic KPI computation (summary stats, breakdown,
                  trend) over a dataset's real table - see module docstrings
  auth/         - identity: registration, login, password hashing (Argon2id),
                  JWT issuance/verification, get_current_user dependency
  rbac/         - authorization: roles/permissions catalog + seeding,
                  effective-permission resolution, require_permission(...)
  audit/        - centralized audit event recording + querying
  ml/           - classical ML: suitability, feature engineering, one
                  module per task (classification/forecasting/segmentation/
                  anomaly_detection), explainability, artifacts, service
                  orchestration - see app/ml/__init__.py's module map
migrations/     - Alembic environment and version history
scripts/        - bootstrap_admin.py (dev-only first-admin creation)
tests/          - pytest suite (tests/auth/, tests/rbac/, tests/audit/,
                  tests/ml/ for their respective phases; the `client`
                  fixture is admin-authenticated by default, so every
                  pre-Phase-4 test kept working unchanged)
tests/fixtures/ - small synthetic datasets used by the ingestion/KPI/ML
                  tests (ml_*.csv are dedicated to Phase 5, never a reused
                  or modified Phase 2 fixture)
```

## Known security limitations (Phase 4, disclosed not hidden)

- **No rate limiting / brute-force lockout** on `/auth/login`. Would
  normally need Redis or similar for distributed rate limiting - explicitly
  out of scope per this project's "no Redis unless genuinely required" rule.
- **No email verification** on registration - any syntactically valid email
  is accepted immediately. Fine for a local/portfolio system, not for a
  real multi-tenant product.
- **Password policy is minimum-length only** (8 characters) - no
  complexity/breach-list checks. A reasonable simplification for this scope.
- **No password reset / "forgot password" flow.**
- **CSRF protection isn't implemented, deliberately** - CSRF is a
  cookie-session concern; this app authenticates via a Bearer token in an
  `Authorization` header (never a cookie), which isn't attacker-settable
  cross-site the way a cookie is, so the standard CSRF attack doesn't apply
  here. It would become relevant if token storage ever moved to cookies.

## Known warning (non-blocking)

`pytest` currently prints a `StarletteDeprecationWarning` about `httpx` vs.
`httpx2` when using FastAPI's `TestClient`. This comes from the installed
`starlette`/`fastapi` versions, not from our code, and doesn't affect test
results. Not addressed in Phase 1; revisit if it becomes a hard failure in
a future dependency bump.

`pytest` also prints a `DeprecationWarning` from inside `joblib`'s own
pickling code (`numpy_pickle.py`, `array.shape = self.shape`) whenever an ML
run's artifact is saved/loaded, triggered by the installed `numpy`/`joblib`
version combination - third-party internals, not our code; joblib 1.5.3 is
already the latest release. Harmless; revisit only if a future joblib
release resolves it upstream.
