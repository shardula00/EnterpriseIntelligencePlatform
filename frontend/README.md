# frontend/

React + TypeScript + Vite + Tailwind app (Phase 3). Talks to the backend
exclusively through its REST API, using a client typed against the
backend's real OpenAPI schema - no business logic lives here beyond
presentation and interaction state. Phase 4 added authentication
(login/register/logout), protected routes, and role-aware UI - see
"Authentication (Phase 4)" below. Phase 5 added a `/ml` section - task
selection, dataset suitability, per-task training configuration, model
comparison, and predictions - see "Classical ML (Phase 5)" below.

## Prerequisites

- Node.js 20+ and npm
- The backend running locally (see [../backend/README.md](../backend/README.md))
  with Postgres up via `infra/docker-compose.yml`

## First-time setup

```powershell
cd frontend
npm install
cp .env.example .env
# .env's VITE_API_BASE_URL defaults to http://localhost:8000, matching
# the backend's default port - only change it if you run the backend
# elsewhere.
```

## Running the app

With the backend already running (`uvicorn app.main:app --reload` from
`backend/`, Postgres up via Docker Compose):

```powershell
npm run dev
```

Visit `http://localhost:5173`. You'll land on `/login` (Phase 4: every
application route requires authentication). Register an account (starts
as Viewer) or sign in as the bootstrap admin (see
[../backend/README.md](../backend/README.md#authentication--rbac-phase-4)),
then upload a CSV/Excel/JSON file (e.g.
`backend/tests/fixtures/orders_sample.csv`) and explore its Overview
(KPIs), Schema, Quality, Preview, and Lineage tabs.

## Authentication (Phase 4)

- **`/login` and `/register`** are the only public routes; everything else
  is wrapped in `ProtectedRoute` (redirects to `/login` if unauthenticated)
  or `RequirePermission` (redirects home if authenticated but not
  permitted - used for `/admin/users` and `/admin/audit`).
- **`AuthContext`** (`src/auth/AuthContext.tsx`) holds the current user and
  exposes `login`/`register`/`logout`; `usePermission(name)`
  (`src/hooks/usePermission.ts`) is the UX-only check components use to
  decide what to show (e.g. hiding the dataset Delete button, or the
  Breakdown/Trend charts, for a Viewer). **The backend independently
  enforces every one of these** - hiding a control here only improves UX,
  it is never the security boundary; the Phase 4 E2E pass explicitly
  confirms the backend rejects a Viewer's delete attempt via a raw `fetch`
  call bypassing the UI entirely, not just that the button is hidden.
- **Token storage: `localStorage`** (`src/auth/tokenStorage.ts`) - a
  deliberate portfolio-scale tradeoff, not an oversight. A token readable
  by `localStorage` is also readable by any script that gets injected into
  the page (XSS), which an `httpOnly` cookie would prevent. This app
  accepted that tradeoff because: the token is short-lived (60 minutes, no
  refresh token to steal for long-term persistence); the app renders no
  user-supplied HTML anywhere (no current XSS sink); and building
  `httpOnly` + `Secure` + `SameSite` cookies with CSRF protection is real
  additional infrastructure that wasn't justified for this phase. A
  production system handling more sensitive data should use that cookie
  approach instead - noted here as a real, known limitation, not
  minimized.
- **On any `401`**, the API client (`src/api/client.ts`) clears the stored
  token and dispatches an `eip:unauthorized` event; `AuthContext` listens
  for it and resets to the logged-out state, so an expired or
  server-invalidated token (logout elsewhere, admin deactivation) is
  caught on the very next request, not just at the next page load.

## Classical ML (Phase 5)

The `/ml` section (gated by `ml:read`; training additionally needs
`ml:train`, predictions need `ml:predict` - see `backend/README.md`'s
Phase 5 section for the permission catalog):

- **`/ml`** - task selection (4 cards: Binary Classification, Time-Series
  Forecasting, Customer Segmentation, Anomaly Detection) plus a recent-runs
  list.
- **`/ml/:taskType`** - dataset selection for that task: every uploaded
  dataset shown with a real suitability check (one `GET .../ml/suitability`
  call per dataset, since that endpoint reports all 4 tasks at once) -
  suitable datasets link to the configure page, unsuitable ones show the
  backend's actual rejection reason and aren't clickable.
- **`/ml/:taskType/:datasetId`** - a per-task configuration form
  (`ClassificationConfigForm`/`ForecastConfigForm`/`SegmentationConfigForm`/
  `AnomalyConfigForm` in `src/components/ml/`), pre-filled with the
  backend's suggested columns but fully editable, that trains a real model
  and navigates to its results on success.
- **`/ml/runs/:runId`** - results for one run, dispatched to a per-task
  view (`ClassificationResultsView`/`ForecastResultsView`/
  `SegmentationResultsView`/`AnomalyResultsView`) covering model comparison,
  metrics, and task-specific visualization (confusion matrix + feature
  importance for classification; historical/forecast chart with confidence
  band for forecasting; cluster size/feature-mean charts for segmentation;
  anomaly score chart + flagged-record table for anomaly detection) - plus
  a `PredictAction` that calls the real predict endpoint and renders its
  real response.
- **`/ml/runs`** - full run history across every task.

The union type `MLRunResultsOut.results` (see backend's Phase 5 notes) is
generated as a real 4-member Pydantic union, not `dict[string, unknown]` -
`frontend/src/api/types.ts` narrows it to the concrete result type using
the sibling `run.task_type` field via `isClassificationResults()` /
`isForecastResults()` / `isSegmentationResults()` / `isAnomalyResults()`
(and the equivalent `is*Predictions()` helpers for prediction responses),
documented inline as to why that narrowing pattern exists instead of a
schema-level discriminator.

## Regenerating the typed API client

Whenever the backend's routes or response models change, regenerate the
types (requires the backend running):

```powershell
npm run generate:api
```

This rewrites `src/api/schema.d.ts` from `http://localhost:8000/openapi.json`.
`src/api/client.ts` wraps it with one typed function per endpoint
(`getDatasets`, `uploadDataset`, `getKpiSummary`, etc.) - components only
ever call those, never `fetch` directly.

## Tests

```powershell
npm test          # run once
npm run test:watch # watch mode
```

Component tests mock the API client module (`vi.mock('.../api/client')`)
so they run without a live backend - the running *app* always talks to
the real API; only these isolated unit tests substitute canned responses,
which is standard practice for frontend component testing.

## Linting & build

```powershell
npm run lint   # oxlint
npm run build  # tsc -b && vite build
```

## Layout

```
src/
  api/
    schema.d.ts   - generated from the backend's OpenAPI schema (see above)
    client.ts     - typed fetch wrapper, the ONLY place that calls the network
                    (also injects the Bearer token and handles 401s - Phase 4)
    types.ts      - convenience aliases onto the generated component schemas
  auth/
    AuthContext.tsx   - current user, login/register/logout, loading state
    tokenStorage.ts   - localStorage token persistence (see tradeoff above)
  hooks/
    useAsync.ts        - small loading/success/error data-fetching hook
    usePermission.ts   - UX-only permission check (see Authentication above)
  components/
    layout/            - AppShell (nav + page frame; role-aware nav links, Phase 4)
    routing/            - ProtectedRoute, RequirePermission (Phase 4)
    upload/             - UploadDropzone
    datasets/           - DatasetList (Delete button gated by dataset:delete), QualityScoreBadge
    dataset-detail/     - SchemaTable, QualityPanel, PreviewTable, LineageTimeline
    dataset-detail/kpi/ - KpiDashboard (Breakdown/Trend gated by dashboard:configure), StatTile, BreakdownChart, TrendChart
    ml/                 - Phase 5: task metadata, 4 config forms, 4 results
                          views, shared charts (CandidateModelTable,
                          FeatureImportanceChart, ConfusionMatrix,
                          ForecastChart, ClusterCharts, AnomalyScoreChart),
                          FeatureColumnPicker, PredictAction
    common/             - LoadingSpinner, ErrorMessage, EmptyState
  pages/
    DatasetsPage.tsx        - upload + dataset list ("/")
    DatasetDetailPage.tsx   - tabbed dataset detail ("/datasets/:datasetId")
    LoginPage.tsx, RegisterPage.tsx  - Phase 4
    admin/UsersPage.tsx     - user management ("/admin/users", user:read)
    admin/AuditLogPage.tsx  - audit log viewer ("/admin/audit", audit:read)
    ml/                     - Phase 5: MlTaskSelectionPage ("/ml"),
                              MlDatasetSelectionPage ("/ml/:taskType"),
                              MlConfigurePage ("/ml/:taskType/:datasetId"),
                              MlRunPage ("/ml/runs/:runId"),
                              MlRunsHistoryPage ("/ml/runs")
  test/
    renderWithProviders.tsx  - render helper wrapping MemoryRouter + AuthProvider
    authTestUtils.ts         - fakeUser()/setFakeToken() for auth-aware component tests
```

## Known limitations

**Phase 3:**
- The KPI dashboard's default breakdown/trend/metric selections are the
  first column that qualifies, not necessarily the most "interesting"
  one for a given dataset - the dropdowns let you pick a better one in
  one click, but there's no smarter auto-selection yet.
- No production build has been deployed anywhere; `npm run build`
  produces a static bundle but nothing serves it yet outside local `preview`.

**Phase 4:**
- Token storage is `localStorage`, not an `httpOnly` cookie - see
  "Authentication (Phase 4)" above for the full tradeoff writeup.
- No password-strength meter or "forgot password" flow in the UI (the
  backend also doesn't implement password reset - see backend/README.md's
  security limitations).
- The admin Users page lets an admin assign multiple roles via checkboxes,
  but the create-user form is intentionally minimal (name/email/password
  only, always starts as Viewer) - role assignment is a separate,
  deliberate follow-up action, not part of creation.

**Phase 5:**
- Training blocks the whole configure-page form until the backend responds
  (no progress bar/percentage - the backend itself trains synchronously,
  see backend/README.md's Phase 5 section) - acceptable at this project's
  dataset sizes, flagged as a Phase 6 concern if that changes.
- Segmentation's per-cluster visualization is a feature-means bar chart,
  not a 2D scatter plot - a genuine scatter would need dimensionality
  reduction (PCA/t-SNE) for datasets with more than 2 feature columns,
  which wasn't justified for this phase; the bar chart generalizes to any
  number of features without that added complexity.
- No way to re-run a training job with different settings from the results
  page directly - going back to the configure page and submitting again
  creates a new, independent run rather than an editable one (consistent
  with runs being immutable once trained).
