#!/usr/bin/env bash
# Phase 13: post-deployment smoke test - checks the real public URLs after
# a deploy, mirroring the Phase 12 local `docker compose up --build` smoke
# test (see README.md's "Running the full stack with Docker Compose"), now
# pointed at production. Run from .github/workflows/deploy.yml after the
# SSM Run Command restart step; exits non-zero (failing the workflow) if
# either endpoint doesn't come up healthy within the retry window.
#
# Usage: APP_URL=https://app.example.com API_URL=https://api.example.com ./smoke_test.sh
set -euo pipefail

APP_URL="${APP_URL:?Set APP_URL, e.g. https://app.example.com}"
API_URL="${API_URL:?Set API_URL, e.g. https://api.example.com}"
MAX_ATTEMPTS=12
SLEEP_SECONDS=10

# $3: optional substring the response body must contain (skipped if empty,
# in which case only a 200 status is required) - body checks are only used
# where the contract is stable/documented (the /health JSON shape), not
# against frontend markup that could reasonably change.
check() {
  local name="$1" url="$2" expect="${3:-}"
  local attempt=1
  while [ "${attempt}" -le "${MAX_ATTEMPTS}" ]; do
    if body="$(curl -fsS --max-time 10 "${url}")"; then
      if [ -z "${expect}" ] || [[ "${body}" == *"${expect}"* ]]; then
        echo "OK   ${name} (${url}) - attempt ${attempt}"
        return 0
      fi
    fi
    echo "wait ${name} (${url}) - attempt ${attempt}/${MAX_ATTEMPTS}"
    attempt=$((attempt + 1))
    sleep "${SLEEP_SECONDS}"
  done
  echo "FAIL ${name} (${url}) did not become healthy after $((MAX_ATTEMPTS * SLEEP_SECONDS))s"
  return 1
}

status=0
check "backend /health" "${API_URL}/health" '"status":"ok"' || status=1
check "frontend /healthz" "${APP_URL}/healthz" "ok" || status=1
check "frontend /" "${APP_URL}/" || status=1

exit "${status}"
