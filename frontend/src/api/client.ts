/**
 * Typed API client for the backend, built from its real OpenAPI schema
 * (see schema.d.ts - regenerate with `npm run generate:api` whenever the
 * backend's routes/models change).
 *
 * This is the ONLY place the frontend talks to the network - components
 * never call `fetch` directly, so every request/response shape is checked
 * by the TypeScript compiler against what FastAPI actually returns.
 */
import createClient from 'openapi-fetch'
import type { paths } from './schema'
import { clearToken, dispatchUnauthorized, getToken, setToken } from '../auth/tokenStorage'

const baseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

const client = createClient<paths>({ baseUrl })

client.use({
  onRequest({ request }) {
    const token = getToken()
    if (token) {
      request.headers.set('Authorization', `Bearer ${token}`)
    }
    return request
  },
  onResponse({ response }) {
    if (response.status === 401) {
      clearToken()
      dispatchUnauthorized()
    }
    return response
  },
})

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Throws ApiError with the backend's `detail` message on any non-2xx response. */
function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data !== undefined) return result.data
  const detail =
    typeof result.error === 'object' && result.error !== null && 'detail' in result.error
      ? String((result.error as { detail?: unknown }).detail)
      : `Request failed with status ${result.response.status}`
  throw new ApiError(detail, result.response.status)
}

// ---------------------------------------------------------------------------
// Auth (Phase 4)
// ---------------------------------------------------------------------------

export async function authRegister(email: string, password: string, fullName: string) {
  const result = await client.POST('/auth/register', {
    body: { email, password, full_name: fullName },
  })
  return unwrap(result)
}

export async function authLogin(email: string, password: string) {
  const result = await client.POST('/auth/login', { body: { email, password } })
  const token = unwrap(result)
  setToken(token.access_token)
  return token
}

export async function authMe() {
  const result = await client.GET('/auth/me')
  return unwrap(result)
}

export async function authLogout() {
  try {
    await client.POST('/auth/logout')
  } finally {
    // Always clear locally, even if the request itself failed (e.g. the
    // token was already invalid) - logging out must never get "stuck".
    clearToken()
  }
}

// ---------------------------------------------------------------------------
// User management (Phase 4, admin)
// ---------------------------------------------------------------------------

export async function listUsers() {
  const result = await client.GET('/users')
  return unwrap(result)
}

export async function getUser(userId: string) {
  const result = await client.GET('/users/{user_id}', { params: { path: { user_id: userId } } })
  return unwrap(result)
}

export async function createUser(email: string, password: string, fullName: string) {
  const result = await client.POST('/users', { body: { email, password, full_name: fullName } })
  return unwrap(result)
}

export async function updateUser(
  userId: string,
  changes: { fullName?: string; isActive?: boolean },
) {
  const result = await client.PATCH('/users/{user_id}', {
    params: { path: { user_id: userId } },
    body: { full_name: changes.fullName ?? null, is_active: changes.isActive ?? null },
  })
  return unwrap(result)
}

export async function assignRoles(userId: string, roleNames: string[]) {
  const result = await client.POST('/users/{user_id}/roles', {
    params: { path: { user_id: userId } },
    body: { role_names: roleNames },
  })
  return unwrap(result)
}

export async function deleteUser(userId: string) {
  const result = await client.DELETE('/users/{user_id}', {
    params: { path: { user_id: userId } },
  })
  if (result.error) unwrap(result)
}

export async function listRoles() {
  const result = await client.GET('/roles')
  return unwrap(result)
}

export async function listPermissions() {
  const result = await client.GET('/permissions')
  return unwrap(result)
}

// ---------------------------------------------------------------------------
// Audit log (Phase 4)
// ---------------------------------------------------------------------------

export async function listAuditLogs(params: {
  limit?: number
  offset?: number
  action?: string
  resourceType?: string
  userId?: string
} = {}) {
  const result = await client.GET('/audit-logs', {
    params: {
      query: {
        limit: params.limit,
        offset: params.offset,
        action: params.action,
        resource_type: params.resourceType,
        user_id: params.userId,
      },
    },
  })
  return unwrap(result)
}

// ---------------------------------------------------------------------------
// Datasets (Phase 2)
// ---------------------------------------------------------------------------

export async function uploadDataset(file: File, datasetName?: string) {
  const result = await client.POST('/datasets/upload', {
    // The real request body is built by bodySerializer below; this object
    // only exists to satisfy the generated (multipart) request type.
    body: { file: file as unknown as string, dataset_name: datasetName ?? null },
    bodySerializer() {
      const formData = new FormData()
      formData.append('file', file)
      if (datasetName) formData.append('dataset_name', datasetName)
      return formData
    },
  })
  return unwrap(result)
}

export async function listDatasets() {
  const result = await client.GET('/datasets')
  return unwrap(result)
}

export async function getDataset(datasetId: string) {
  const result = await client.GET('/datasets/{dataset_id}', { params: { path: { dataset_id: datasetId } } })
  return unwrap(result)
}

export async function deleteDataset(datasetId: string) {
  const result = await client.DELETE('/datasets/{dataset_id}', {
    params: { path: { dataset_id: datasetId } },
  })
  if (result.error) unwrap(result)
}

export async function getColumns(datasetId: string) {
  const result = await client.GET('/datasets/{dataset_id}/columns', {
    params: { path: { dataset_id: datasetId } },
  })
  return unwrap(result)
}

export async function getQuality(datasetId: string) {
  const result = await client.GET('/datasets/{dataset_id}/quality', {
    params: { path: { dataset_id: datasetId } },
  })
  return unwrap(result)
}

export async function getLineage(datasetId: string) {
  const result = await client.GET('/datasets/{dataset_id}/lineage', {
    params: { path: { dataset_id: datasetId } },
  })
  return unwrap(result)
}

export async function getPreview(datasetId: string, limit = 20) {
  const result = await client.GET('/datasets/{dataset_id}/preview', {
    params: { path: { dataset_id: datasetId }, query: { limit } },
  })
  return unwrap(result)
}

// ---------------------------------------------------------------------------
// KPIs (Phase 3)
// ---------------------------------------------------------------------------

export async function getKpiSummary(datasetId: string) {
  const result = await client.GET('/datasets/{dataset_id}/kpis', {
    params: { path: { dataset_id: datasetId } },
  })
  return unwrap(result)
}

export async function getBreakdown(
  datasetId: string,
  groupBy: string,
  metric: string | undefined,
  agg: string,
) {
  const result = await client.GET('/datasets/{dataset_id}/kpis/breakdown', {
    params: { path: { dataset_id: datasetId }, query: { group_by: groupBy, metric, agg } },
  })
  return unwrap(result)
}

export async function getTrend(
  datasetId: string,
  dateColumn: string,
  metric: string,
  granularity: string,
  agg: string,
) {
  const result = await client.GET('/datasets/{dataset_id}/kpis/trend', {
    params: {
      path: { dataset_id: datasetId },
      query: { date_column: dateColumn, metric, granularity, agg },
    },
  })
  return unwrap(result)
}

// ---------------------------------------------------------------------------
// Classical ML (Phase 5)
// ---------------------------------------------------------------------------

export async function getMlSuitability(datasetId: string) {
  const result = await client.GET('/datasets/{dataset_id}/ml/suitability', {
    params: { path: { dataset_id: datasetId } },
  })
  return unwrap(result)
}

export async function trainClassification(body: {
  datasetId: string
  targetColumn: string
  featureColumns?: string[] | null
  testSize?: number
  randomSeed?: number | null
}) {
  const result = await client.POST('/ml/train/classification', {
    body: {
      dataset_id: body.datasetId,
      target_column: body.targetColumn,
      feature_columns: body.featureColumns ?? null,
      test_size: body.testSize ?? 0.25,
      random_seed: body.randomSeed ?? null,
    },
  })
  return unwrap(result)
}

export async function trainForecasting(body: {
  datasetId: string
  datetimeColumn: string
  targetColumn: string
  horizon?: number
  randomSeed?: number | null
}) {
  const result = await client.POST('/ml/train/forecasting', {
    body: {
      dataset_id: body.datasetId,
      datetime_column: body.datetimeColumn,
      target_column: body.targetColumn,
      horizon: body.horizon ?? 14,
      random_seed: body.randomSeed ?? null,
    },
  })
  return unwrap(result)
}

export async function trainSegmentation(body: {
  datasetId: string
  featureColumns?: string[] | null
  nClusters?: number
  randomSeed?: number | null
}) {
  const result = await client.POST('/ml/train/segmentation', {
    body: {
      dataset_id: body.datasetId,
      feature_columns: body.featureColumns ?? null,
      n_clusters: body.nClusters ?? 4,
      random_seed: body.randomSeed ?? null,
    },
  })
  return unwrap(result)
}

export async function trainAnomalyDetection(body: {
  datasetId: string
  featureColumns?: string[] | null
  contamination?: number
  randomSeed?: number | null
}) {
  const result = await client.POST('/ml/train/anomaly-detection', {
    body: {
      dataset_id: body.datasetId,
      feature_columns: body.featureColumns ?? null,
      contamination: body.contamination ?? 0.05,
      random_seed: body.randomSeed ?? null,
    },
  })
  return unwrap(result)
}

export async function listMlRuns(params: { datasetId?: string; taskType?: string } = {}) {
  const result = await client.GET('/ml/runs', {
    params: { query: { dataset_id: params.datasetId, task_type: params.taskType } },
  })
  return unwrap(result)
}

export async function getMlRun(runId: string) {
  const result = await client.GET('/ml/runs/{run_id}', { params: { path: { run_id: runId } } })
  return unwrap(result)
}

export async function predictMlRun(runId: string, horizon?: number) {
  const result = await client.POST('/ml/runs/{run_id}/predict', {
    params: { path: { run_id: runId } },
    body: { horizon: horizon ?? null },
  })
  return unwrap(result)
}

// ---------------------------------------------------------------------------
// MLOps: model registry, drift detection, performance monitoring (Phase 6)
// ---------------------------------------------------------------------------

export async function registerModelVersion(mlRunId: string) {
  const result = await client.POST('/mlops/model-versions', { body: { ml_run_id: mlRunId } })
  return unwrap(result)
}

export async function listModelVersions(
  params: { datasetId?: string; taskType?: string; status?: string } = {},
) {
  const result = await client.GET('/mlops/model-versions', {
    params: {
      query: { dataset_id: params.datasetId, task_type: params.taskType, status: params.status },
    },
  })
  return unwrap(result)
}

export async function getModelVersion(versionId: string) {
  const result = await client.GET('/mlops/model-versions/{version_id}', {
    params: { path: { version_id: versionId } },
  })
  return unwrap(result)
}

export async function promoteModelVersion(versionId: string, targetStatus: 'staging' | 'production') {
  const result = await client.POST('/mlops/model-versions/{version_id}/promote', {
    params: { path: { version_id: versionId } },
    body: { target_status: targetStatus },
  })
  return unwrap(result)
}

export async function archiveModelVersion(versionId: string) {
  const result = await client.POST('/mlops/model-versions/{version_id}/archive', {
    params: { path: { version_id: versionId } },
  })
  return unwrap(result)
}

export async function runDriftCheck(versionId: string, datasetId: string) {
  const result = await client.POST('/mlops/model-versions/{version_id}/drift-check', {
    params: { path: { version_id: versionId } },
    body: { dataset_id: datasetId },
  })
  return unwrap(result)
}

export async function runPerformanceCheck(versionId: string, datasetId: string) {
  const result = await client.POST('/mlops/model-versions/{version_id}/performance-check', {
    params: { path: { version_id: versionId } },
    body: { dataset_id: datasetId },
  })
  return unwrap(result)
}

export async function listMonitoringEvents(
  params: { modelVersionId?: string; eventType?: string; severity?: string } = {},
) {
  const result = await client.GET('/mlops/monitoring-events', {
    params: {
      query: {
        model_version_id: params.modelVersionId,
        event_type: params.eventType,
        severity: params.severity,
      },
    },
  })
  return unwrap(result)
}

// ---------------------------------------------------------------------------
// Enterprise RAG: documents, chunks, query (Phase 7)
// ---------------------------------------------------------------------------

export async function uploadDocument(file: File) {
  const result = await client.POST('/documents/upload', {
    // Same real-body-built-by-bodySerializer pattern as uploadDataset above.
    body: { file: file as unknown as string },
    bodySerializer() {
      const formData = new FormData()
      formData.append('file', file)
      return formData
    },
  })
  return unwrap(result)
}

export async function listDocuments(status?: string) {
  const result = await client.GET('/documents', { params: { query: { status } } })
  return unwrap(result)
}

export async function getDocument(documentId: string) {
  const result = await client.GET('/documents/{document_id}', {
    params: { path: { document_id: documentId } },
  })
  return unwrap(result)
}

export async function processDocument(documentId: string) {
  const result = await client.POST('/documents/{document_id}/process', {
    params: { path: { document_id: documentId } },
  })
  return unwrap(result)
}

export async function deleteDocument(documentId: string) {
  const result = await client.DELETE('/documents/{document_id}', {
    params: { path: { document_id: documentId } },
  })
  if (result.error) unwrap(result)
}

export async function runRagQuery(body: {
  question: string
  documentIds?: string[]
  topK?: number
}) {
  const result = await client.POST('/rag/query', {
    body: {
      question: body.question,
      document_ids: body.documentIds ?? null,
      top_k: body.topK ?? null,
    },
  })
  return unwrap(result)
}

export async function listRagQueries() {
  const result = await client.GET('/rag/queries')
  return unwrap(result)
}

export async function getRagQuery(queryId: string) {
  const result = await client.GET('/rag/queries/{query_id}', {
    params: { path: { query_id: queryId } },
  })
  return unwrap(result)
}

// ---------------------------------------------------------------------------
// Natural-language analytics (Phase 8)
// ---------------------------------------------------------------------------

export async function runAnalyticsQuery(datasetId: string, question: string) {
  const result = await client.POST('/analytics/query', {
    body: { dataset_id: datasetId, question },
  })
  return unwrap(result)
}

export async function listAnalyticsQueries(datasetId?: string) {
  const result = await client.GET('/analytics/queries', {
    params: { query: { dataset_id: datasetId } },
  })
  return unwrap(result)
}

export async function getAnalyticsQuery(queryId: string) {
  const result = await client.GET('/analytics/queries/{query_id}', {
    params: { path: { query_id: queryId } },
  })
  return unwrap(result)
}
