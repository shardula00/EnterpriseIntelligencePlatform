# backend/

FastAPI backend for the Enterprise Intelligence Platform. As of Phase 1,
this contains only the foundational plumbing: settings, a database
connection, one placeholder table, migrations, and a health check. Domain
features (ingestion, BI, ML, RAG, etc.) arrive in later phases per
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

## Layout

```
app/
  main.py       - FastAPI app + router registration
  config.py     - Pydantic Settings, loaded from environment/.env
  db.py         - SQLAlchemy engine, session factory, declarative Base
  models/       - ORM models (import every model in models/__init__.py so
                  Alembic autogenerate can see it)
  api/          - API routers, one module per concern
migrations/     - Alembic environment and version history
tests/          - pytest suite
```

## Known warning (non-blocking)

`pytest` currently prints a `StarletteDeprecationWarning` about `httpx` vs.
`httpx2` when using FastAPI's `TestClient`. This comes from the installed
`starlette`/`fastapi` versions, not from our code, and doesn't affect test
results. Not addressed in Phase 1; revisit if it becomes a hard failure in
a future dependency bump.
