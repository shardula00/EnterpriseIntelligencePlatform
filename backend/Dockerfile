# Phase 12: containerized backend, for `docker compose up` local bring-up
# only (see infra/docker-compose.yml). Not a deployment artifact yet - image
# publishing/registry push is explicitly deferred to Phase 13.
#
# Single-stage, python:3.12-slim: every runtime dependency in requirements.txt
# (psycopg[binary], scikit-learn, pandas, etc.) ships prebuilt Linux wheels,
# so no compiler toolchain is needed in the image.
FROM python:3.12-slim

WORKDIR /app

# curl is only needed so the HEALTHCHECK below can probe GET /health from
# inside the container without adding a Python HTTP dependency for it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Runtime dependencies only (requirements.txt), not requirements-dev.txt -
# pytest/ruff/pytest-cov/pip-audit have no reason to ship in the runtime
# image; they run in CI and locally against the venv instead.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# /health (app/api/health.py) checks real DB connectivity, not just process
# liveness - a green healthcheck here is evidence Postgres is reachable too.
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=6 \
    CMD curl -f http://localhost:8000/health || exit 1

# Apply migrations, then attempt the existing idempotent admin bootstrap
# (scripts/bootstrap_admin.py already refuses safely and exits non-zero if
# BOOTSTRAP_ADMIN_PASSWORD isn't set - `|| true` means a container without
# it configured still starts the API, it just has no admin user yet), then
# serve. Kept as a Dockerfile CMD rather than a separate .sh entrypoint
# file: this repo is checked out on Windows, where a committed shell script
# risks CRLF line endings that fail with a Linux container's /bin/sh.
CMD alembic upgrade head && (python -m scripts.bootstrap_admin || true) && uvicorn app.main:app --host 0.0.0.0 --port 8000
