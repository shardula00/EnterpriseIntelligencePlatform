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
