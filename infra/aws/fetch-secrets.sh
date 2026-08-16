#!/usr/bin/env bash
# Phase 13: pulls every parameter under /eip/prod (secrets as SecureString,
# plus the one non-secret value, ecr_registry, as a plain String - one
# mechanism for everything docker-compose.prod.yml needs) from AWS SSM
# Parameter Store into a local env file - runs ON THE EC2 INSTANCE
# only (via SSM Run Command as part of the deploy workflow, or manually via
# SSM Session Manager), never in CI and never on a developer machine.
#
# Auth: the instance's IAM role (see README.md's ec2-instance-role-policy.json)
# grants ssm:GetParametersByPath + kms:Decrypt scoped to /eip/prod/* only -
# no AWS access keys are read from or written to disk by this script.
#
# Output: .env.prod in the same directory as this script, mode 600,
# regenerated on every run. Never committed (matches infra/.env's *.env.*
# .gitignore pattern) and never hand-edited - SSM Parameter Store is the
# single source of truth for every value it writes.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env.prod"
SSM_PATH="/eip/prod"

echo "Fetching parameters from SSM Parameter Store (${SSM_PATH})..."

# Each parameter's SSM name (e.g. /eip/prod/jwt_secret_key) becomes an
# upper-cased env var (JWT_SECRET_KEY) - matches the exact env var names
# Settings (app/config.py) and docker-compose.prod.yml already expect.
umask 077
: > "${ENV_FILE}"

aws ssm get-parameters-by-path \
  --path "${SSM_PATH}" \
  --with-decryption \
  --recursive \
  --query "Parameters[].{Name:Name,Value:Value}" \
  --output json |
  python3 -c '
import json, sys
params = json.load(sys.stdin)
if not params:
    sys.exit("No parameters found under /eip/prod - has infra/aws/README.md step 6 been completed?")
for p in params:
    name = p["Name"].rsplit("/", 1)[-1].upper()
    value = p["Value"].replace("\n", "\\n")
    print(f"{name}={value}")
' >> "${ENV_FILE}"

chmod 600 "${ENV_FILE}"
echo "Wrote $(wc -l < "${ENV_FILE}") parameter(s) to ${ENV_FILE}"
