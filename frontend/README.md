# frontend/

React + TypeScript + Vite + Tailwind app (Phase 3). Talks to the backend
exclusively through its REST API, using a client typed against the
backend's real OpenAPI schema - no business logic lives here beyond
presentation and interaction state.

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

Visit `http://localhost:5173`. Upload a CSV/Excel/JSON file (e.g.
`backend/tests/fixtures/orders_sample.csv`) and explore its Overview
(KPIs), Schema, Quality, Preview, and Lineage tabs.

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
    types.ts      - convenience aliases onto the generated component schemas
  hooks/
    useAsync.ts   - small loading/success/error data-fetching hook
  components/
    layout/            - AppShell (nav + page frame)
    upload/             - UploadDropzone
    datasets/           - DatasetList, QualityScoreBadge
    dataset-detail/     - SchemaTable, QualityPanel, PreviewTable, LineageTimeline
    dataset-detail/kpi/ - KpiDashboard, StatTile, BreakdownChart, TrendChart
    common/             - LoadingSpinner, ErrorMessage, EmptyState
  pages/
    DatasetsPage.tsx       - upload + dataset list ("/")
    DatasetDetailPage.tsx  - tabbed dataset detail ("/datasets/:datasetId")
```

## Known limitations (Phase 3)

- The KPI dashboard's default breakdown/trend/metric selections are the
  first column that qualifies, not necessarily the most "interesting"
  one for a given dataset - the dropdowns let you pick a better one in
  one click, but there's no smarter auto-selection yet.
- No authentication (not required until Phase 4) - the API and UI are
  both fully open.
- No production build has been deployed anywhere; `npm run build`
  produces a static bundle but nothing serves it yet outside local `preview`.
