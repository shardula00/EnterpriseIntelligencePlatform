# Security

Phase 12 deliverable: a factual, living record of this platform's security
posture - what's enforced, what's been checked, what's a deliberate
tradeoff, and how to re-run every check yourself. This is not a compliance
template; every claim below is backed by a test, a scan result, or a cited
line of code, and is updated whenever the underlying reality changes.

## 1. RBAC route coverage

Every registered API route is either explicitly public (and listed below)
or requires authentication/a specific permission. This isn't just a manual
review - it's an automated, standing regression test:
[`backend/tests/rbac/test_route_coverage.py`](backend/tests/rbac/test_route_coverage.py)
enumerates every `APIRoute` FastAPI has actually registered and walks its
resolved dependency tree, failing the build the same day a route is ever
added without an auth/permission dependency.

**Result (last run): 60 routes checked, 0 unprotected.**

Intentionally public routes (everything else requires, at minimum, a valid
JWT via `get_current_user`/`get_current_active_user`, and in almost every
case a specific permission via `require_permission(...)` - see
`app/rbac/dependencies.py`):

| Method | Path | Why it's public |
|---|---|---|
| `GET` | `/health` | Liveness/readiness probe (Docker healthcheck, CI, monitoring) - no credential exists to check yet at that layer. |
| `POST` | `/auth/register` | Identity bootstrap - there is no token to present yet. Always grants `VIEWER` only; no way to self-escalate (see §2). |
| `POST` | `/auth/login` | Same reason. Failure responses never distinguish "wrong password" from "no such email" (standard account-enumeration mitigation). |

`/docs`, `/redoc`, `/openapi.json` (FastAPI's own interactive docs) are
also reachable without a token - they describe the API shape, not any
data, and are standard for a project at this stage. If this API is ever
exposed beyond a local/trusted network, disabling them (`FastAPI(docs_url=
None, redoc_url=None, openapi_url=None)`) is a one-line change to make at
that time - not made now, since local-first development benefits from
having them.

## 2. Authentication & authorization design (Phase 4, unchanged by Phase 12)

- **JWTs carry minimal claims**: `sub` (user id), `tv` (token version),
  `iat`, `exp` - no email, name, roles, or permissions. A JWT is base64,
  not encrypted, so anything embedded in it is readable by whoever holds
  it; and *what a user can do* is re-resolved from the database on every
  request (`app/rbac/service.py::has_permission`), never cached in the
  token, so a permission change or revocation takes effect immediately
  rather than waiting for a token to expire.
- **No refresh tokens.** A single 60-minute access token
  (`Settings.jwt_expires_minutes`); revocation is via a per-user
  `token_version` counter - logout and admin-deactivation both increment
  it, and every request is rejected if its token's `tv` claim doesn't
  match the user's current value. **Accepted tradeoff**: this invalidates
  every active session for that user at once, not just the one that
  logged out. Judged acceptable at this project's scale (a solo/small-team
  local platform); a multi-device consumer product would want per-session
  revocation and refresh-token rotation instead.
- **Self-privilege-escalation is blocked by a blanket rule**: an admin
  cannot change their own role assignment or active status through the
  admin API at all (not "cannot increase" - cannot change). Simpler to
  reason about, and impossible to get wrong at the boundary compared to a
  case-by-case check.
- **Registration always grants `VIEWER`**, never anything higher - the
  only way to reach `ANALYST`/`ADMIN` is an existing admin explicitly
  granting it via `POST /users/{user_id}/roles`. This is what makes open
  self-registration safe to leave on.

## 3. Frontend token storage (Phase 4, unchanged by Phase 12)

The frontend stores the JWT in `localStorage`
([`frontend/src/auth/tokenStorage.ts`](frontend/src/auth/tokenStorage.ts)),
not an httpOnly cookie. **Accepted tradeoff, not an oversight**:

- `localStorage` is readable by any JavaScript that runs on the page
  (XSS-exposed) - an httpOnly cookie would not be.
- This is judged acceptable here because: the token is short-lived (60
  minutes, no refresh token to steal for long-term persistence), and the
  app renders no HTML from user-supplied input anywhere (React escapes all
  interpolated content by default; there is no `dangerouslySetInnerHTML`
  in the codebase), which is the primary vector that would turn this into
  a real XSS risk.
- The alternative (httpOnly cookie + CSRF-token machinery) is real,
  well-understood engineering effort that this portfolio-scale project
  chose not to build for a marginal security gain at this trust level -
  revisit if this platform ever needs to run somewhere less trusted than a
  local machine or a small team's internal deployment.

## 4. Development secrets & defaults

- `.env` (backend, and any per-directory `.env`) is gitignored everywhere
  in this repo; only `.env.example` templates (no real values) are
  committed - see `.gitignore`.
- `Settings.jwt_secret_key` has an obviously-fake default
  (`CHANGE-ME-THIS-IS-A-LOCAL-DEV-ONLY-DEFAULT-SECRET`, see
  `app/config.py`) specifically so nobody mistakes it for a real secret -
  fine for a solo local dev machine, but anyone deploying this beyond that
  must set a real, generated one (`python -c "import secrets;
  print(secrets.token_urlsafe(48))"`, documented in `backend/.env.example`
  and `infra/.env.example`).
- `BOOTSTRAP_ADMIN_PASSWORD` has **no default value at all** -
  `scripts/bootstrap_admin.py` refuses to create the first admin account
  without a real one being explicitly set, rather than falling back to a
  guessable password. The same script also runs (optionally, and just as
  safely) inside the Phase 12 backend container's startup - see
  `backend/Dockerfile`.
- No API key (`OPENAI_API_KEY`, etc.) has a default value or is required
  to run the platform - every paid/hosted provider is strictly opt-in
  config (see `app/config.py`'s RAG section and `ARCHITECTURE.md` §6).

## 5. Dependency audit process & results

Run locally with (see each README for the exact commands):

```powershell
# Backend
cd backend
.venv\Scripts\pip-audit -r requirements.txt

# Frontend
cd frontend
npm audit
```

Both also run in CI (`backend-ci.yml`, `frontend-ci.yml`) on every push -
**reported, not hard-gated**: a newly-disclosed CVE in an unrelated
transitive dependency shouldn't block every future PR before a human has
triaged it. Findings are never hidden to make CI green; they're fixed
directly when there's a safe upgrade, or recorded here as an accepted risk
when there isn't.

**Result as of Phase 12 (2026-08-16):**

| Tool | Scope | Result |
|---|---|---|
| `pip-audit 2.10.1` | `backend/requirements.txt`, fully resolved (51 packages, direct + transitive) | **0 known vulnerabilities** |
| `npm audit` | `frontend/package.json`, fully resolved (283 packages, prod + dev + optional) | **0 vulnerabilities** |

No fixes were needed this pass - both scans came back clean. This section
will be updated (with what was found and how it was resolved or accepted)
the next time either tool reports something.

### Known non-vulnerability issue: `openapi-typescript` peer range

`openapi-typescript@7.13.0` declares a peer dependency on
`typescript@^5.x`; this project pins `typescript@~6.0.2`. This is a
**dependency-graph mismatch, not a security vulnerability** (neither audit
tool flags it) - `npm install`/`npm ci` refuse to resolve it strictly, so
both `frontend/Dockerfile` and `frontend-ci.yml` use
`--legacy-peer-deps`. Accepted as a non-issue in practice:
`openapi-typescript` is a devDependency-only, build-time-only CLI codegen
tool (`npm run generate:api`) with no runtime interaction with the
TypeScript compiler API it's declaring a peer range against - it works
correctly against TypeScript 6 despite the stale declared range. Not
"fixed" by downgrading `typescript` project-wide, per this phase's
locked decision against blanket dependency changes unrelated to an actual
vulnerability.

## 6. Test coverage

Coverage is **instrumented and reported, not gated at a hard percentage**.
A numeric floor invites tests written to move a number rather than tests
that verify something real; this project instead uses coverage output to
find genuinely untested branches and add targeted tests for them (see
`DatasetsPage.test.tsx` and `App.test.tsx`, both added this phase after
coverage revealed they had none).

Run locally:

```powershell
# Backend
cd backend
.venv\Scripts\pytest --cov=app --cov-report=term-missing --cov-report=html

# Frontend
cd frontend
npm run test:coverage
```

**Baseline as of Phase 12 (2026-08-16):**

| | Statements | Branches | Functions | Lines |
|---|---|---|---|---|
| Backend (`app/`) | 95% (4802 stmts, 163 missed) | — | — | — |
| Frontend (`src/`) | 77.9% | 75.4% | 76.0% | 79.4% |

(Backend coverage is reported as one combined statement+branch percentage
by `pytest-cov`'s default summary rather than four separate axes - see the
full per-file breakdown in `backend/htmlcov/index.html` or the CI
artifact.)

Full per-file breakdowns are uploaded as CI artifacts
(`backend-coverage`, `frontend-coverage`) on every run, and generated
locally under `backend/htmlcov/` and `frontend/coverage/`.

Two known, deliberately-accepted low-coverage areas, not treated as gaps
to close:

- **`frontend/src/api/client.ts`** - every component test mocks this
  module entirely (`vi.mock('../api/client', ...)`, see
  `frontend/src/test/authTestUtils.ts` and nearly every page/component
  test), by design: it's the project's single network boundary
  (`frontend/README.md`), and tests exercise components against a
  controlled mock rather than a real network call. That means the real
  function bodies in `client.ts` are exercised by every manual/E2E
  verification pass (see each phase's browser walkthrough in
  `DEVELOPMENT_PLAN.md`) but rarely by a unit test directly invoking them -
  an accepted characteristic of the mocking strategy, not a defect.
- Thin, purely-presentational leaf components (icons, static badges) with
  no conditional logic show 100% or near-0% depending on whether a given
  test happens to render them, which is expected noise at this
  granularity and not individually chased.

## 7. Containerized deployment surface (Phase 12)

`docker compose up --build` (from `infra/`) starts the entire local
platform: Postgres+pgvector, the backend API, and the frontend, each with
a healthcheck (`backend/Dockerfile`, `frontend/Dockerfile`,
`infra/docker-compose.yml`). This is **local-only bring-up** - no image is
ever pushed to a registry (Docker Hub, ECR, or otherwise); that's
explicitly deferred to Phase 13 (cloud deployment), per this phase's
locked decision.

- Both Dockerfiles exclude `.env`/secrets from the build context
  (`.dockerignore`) - a real secret is never baked into an image layer.
- The backend container's default `JWT_SECRET_KEY` and unset
  `BOOTSTRAP_ADMIN_PASSWORD` follow the exact same "obviously fake
  default / no default at all" pattern as running outside Docker (§4) -
  containerizing the app does not weaken this in any way.

## 8. What this review deliberately did not add

Consistent with `ARCHITECTURE.md`'s "boring technology where it doesn't
matter" principle and this phase's locked scope:

- No WAF, no rate limiting, no intrusion detection - out of scope for a
  local-first portfolio project; would matter for a real internet-facing
  deployment (Phase 13+).
- No secrets manager for **local development** (Vault, AWS Secrets
  Manager, etc.) - `.env` + `.gitignore` remains the right amount of
  machinery there; production secrets moved to AWS SSM Parameter Store in
  Phase 13 (§9) without changing anything about local dev.
- No SAST/SCA tool beyond `pip-audit`/`npm audit` (e.g. no Snyk, no
  CodeQL) - both chosen audit tools are free, require no account/API key,
  and directly answer "does a resolved dependency have a known CVE," which
  is what this phase's locked decision asked for.

## 9. Production deployment (Phase 13)

Deploys the same containers §7 describes to a single AWS EC2 instance -
see [infra/aws/README.md](infra/aws/README.md) for the full runbook.
**Nothing has been deployed as of this writing**; this section documents
the security posture the design commits to once it is.

- **Secrets**: production secrets (`JWT_SECRET_KEY`, `POSTGRES_PASSWORD`,
  `BOOTSTRAP_ADMIN_PASSWORD`, `BOOTSTRAP_ADMIN_EMAIL`,
  `CORS_ALLOW_ORIGINS`) live in AWS SSM Parameter Store as `SecureString`
  values under `/eip/prod/`, encrypted with the account's default `aws/ssm`
  KMS key. `infra/aws/fetch-secrets.sh` pulls them into a local
  `.env.prod` file **on the EC2 instance only**, generated fresh on every
  deploy, gitignored, mode `600` - never committed, never typed into a
  chat session, never stored as a GitHub secret. Local development is
  completely unaffected and still uses `backend/.env`/`infra/.env`.
- **No long-lived AWS credentials anywhere.** The EC2 instance authenticates
  to SSM/ECR via its IAM instance profile
  (`infra/aws/iam/ec2-instance-role-policy.json`, scoped to `/eip/prod/*`
  and the two `eip-*` ECR repos only - not account-wide). GitHub Actions
  authenticates via OIDC federation
  (`infra/aws/iam/github-oidc-trust-policy.json`, `github-deploy-role-policy.json`)
  - only a role ARN (not a credential) is stored as a GitHub Actions
    repository variable.
- **No inbound SSH.** The security group never opens port 22; all shell
  access is via AWS SSM Session Manager, which needs no inbound port at
  all. Postgres is bound to the instance's own loopback interface only
  (`127.0.0.1:5432`, see `infra/aws/docker-compose.prod.yml`) - not
  reachable from the internet regardless of security-group state, and
  reachable for troubleshooting only via SSM port forwarding.
- **Only ports 80/443 are internet-reachable**, both terminated by a
  Caddy reverse-proxy container - Postgres, the backend, and the frontend
  publish no host ports directly in production (unlike local dev, where
  direct-publish is a deliberate developer convenience with no internet
  exposure to begin with).
- **HTTPS**: Caddy automatically obtains and renews free Let's Encrypt
  certificates once real domains are configured
  (`infra/aws/Caddyfile`) - **on hold until a real domain is provided**,
  per this phase's locked decision; the Caddyfile ships with clearly
  marked placeholder domains that will not obtain a certificate if used
  as-is.
- **Deploys require manual confirmation** (`workflow_dispatch` with a
  typed `deploy` confirmation input, not automatic on push) - a real
  running system and real AWS spend shouldn't change on every push.
- **Backups** (`infra/aws/backup.sh`, daily via `eip-backup.timer`) are a
  `pg_dump` + app-data archive stored on the same EBS volume as the live
  data - protects against application-level mistakes, not against loss of
  the volume/instance itself. Off-instance backup replication (e.g. to
  S3) was intentionally left out of this phase's locked scope; documented
  here as a natural future improvement, not a current gap being hidden.
- **Cost monitoring**: an AWS Budgets alert
  (`infra/aws/budget.json`/`budget-notifications.json`) - both currently
  placeholders (`REPLACE_WITH_YOUR_MONTHLY_LIMIT_USD`,
  `REPLACE_WITH_YOUR_EMAIL`) until a real limit/address is provided; the
  runbook explicitly instructs not running `aws budgets create-budget`
  until they are.
