# backend/

FastAPI backend for the Enterprise Intelligence Platform. Phase 1 added the
foundational plumbing (settings, DB connection, migrations, health check).
Phase 2 added generic dataset ingestion (CSV/Excel/JSON upload -> schema
detection -> profiling -> quality scoring -> a real Postgres table ->
lineage). Phase 3 added a generic KPI engine (`app/bi/`) and CORS support
for the new React frontend. Further domain features (auth, ML, RAG, etc.)
arrive in later phases per [DEVELOPMENT_PLAN.md](../DEVELOPMENT_PLAN.md).

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

```powershell
# Upload one of the committed test fixtures as a quick demo:
curl -X POST http://localhost:8000/datasets/upload -F "file=@tests/fixtures/orders_sample.csv"

# Then, with the returned "id":
curl http://localhost:8000/datasets/<id>
curl http://localhost:8000/datasets/<id>/columns
curl http://localhost:8000/datasets/<id>/quality
curl http://localhost:8000/datasets/<id>/lineage
curl "http://localhost:8000/datasets/<id>/preview?limit=10"
curl -X DELETE http://localhost:8000/datasets/<id>
```

Endpoints: `POST /datasets/upload`, `GET /datasets`, `GET /datasets/{id}`,
`GET /datasets/{id}/columns`, `GET /datasets/{id}/quality`,
`GET /datasets/{id}/lineage`, `GET /datasets/{id}/preview`,
`DELETE /datasets/{id}`.

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
curl http://localhost:8000/datasets/<id>/kpis
curl "http://localhost:8000/datasets/<id>/kpis/breakdown?group_by=category&metric=quantity&agg=sum"
curl "http://localhost:8000/datasets/<id>/kpis/trend?date_column=order_date&metric=quantity&granularity=month&agg=sum"
```

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
migrations/     - Alembic environment and version history
tests/          - pytest suite
tests/fixtures/ - small synthetic datasets used by the ingestion/KPI tests
```

## Known warning (non-blocking)

`pytest` currently prints a `StarletteDeprecationWarning` about `httpx` vs.
`httpx2` when using FastAPI's `TestClient`. This comes from the installed
`starlette`/`fastapi` versions, not from our code, and doesn't affect test
results. Not addressed in Phase 1; revisit if it becomes a hard failure in
a future dependency bump.
