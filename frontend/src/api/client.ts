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

const baseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

const client = createClient<paths>({ baseUrl })

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
