import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AnalyticsPage } from './AnalyticsPage'
import * as apiClient from '../api/client'
import { renderWithProviders } from '../test/renderWithProviders'
import { ANALYST_PERMISSIONS, fakeUser, setFakeToken } from '../test/authTestUtils'
import type { AnalyticsQueryResult, DatasetSummary } from '../api/types'

// A partial mock (keeping the real ApiError class via importActual) rather
// than a full vi.mock('../api/client') automock - automocking replaces
// ApiError with a mock that fails `instanceof` checks, breaking the
// component's `err instanceof ApiError` branch (see
// DocumentUploadForm.test.tsx for the same pattern).
vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client')
  return { ...actual, authMe: vi.fn(), listDatasets: vi.fn(), runAnalyticsQuery: vi.fn() }
})

const dataset: DatasetSummary = {
  id: 'ds-1',
  name: 'phase8_sales',
  original_filename: 'phase8_sales.csv',
  file_type: 'csv',
  storage_schema: 'ingested',
  storage_table_name: 'ds_1',
  row_count: 28,
  column_count: 9,
  quality_score: 100,
  status: 'ready',
  created_at: '2026-01-01T00:00:00Z',
}

const answer: AnalyticsQueryResult = {
  id: 'q-1',
  dataset_id: 'ds-1',
  dataset_name: 'phase8_sales',
  question: 'What is the total revenue?',
  status: 'answered',
  generated_sql: 'SELECT sum(ingested.ds_1.revenue) AS revenue FROM ingested.ds_1',
  intent: 'total',
  error_message: null,
  columns: ['revenue'],
  rows: [{ revenue: 6790000 }],
  row_count: 1,
  created_at: '2026-01-01T00:00:00Z',
}

beforeEach(() => {
  setFakeToken()
  vi.mocked(apiClient.authMe).mockResolvedValue(
    fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
  )
})

describe('AnalyticsPage', () => {
  it('shows an empty state when there are no datasets to select', async () => {
    vi.mocked(apiClient.listDatasets).mockResolvedValue([])
    renderWithProviders(<AnalyticsPage />)
    expect(await screen.findByText('No datasets yet')).toBeInTheDocument()
  })

  it('lets the user pick a dataset, ask a question, and see the answer', async () => {
    vi.mocked(apiClient.listDatasets).mockResolvedValue([dataset])
    vi.mocked(apiClient.runAnalyticsQuery).mockResolvedValue(answer)

    renderWithProviders(<AnalyticsPage />)

    await userEvent.selectOptions(await screen.findByLabelText(/dataset/i), 'ds-1')
    await userEvent.type(screen.getByLabelText(/question/i), 'What is the total revenue?')
    await userEvent.click(screen.getByRole('button', { name: /^ask$/i }))

    expect(await screen.findByText(/SELECT sum/)).toBeInTheDocument()
    expect(screen.getByText('6,790,000')).toBeInTheDocument()
    expect(apiClient.runAnalyticsQuery).toHaveBeenCalledWith('ds-1', 'What is the total revenue?')
  })

  it('shows an error message when the question fails', async () => {
    vi.mocked(apiClient.listDatasets).mockResolvedValue([dataset])
    vi.mocked(apiClient.runAnalyticsQuery).mockRejectedValue(
      new apiClient.ApiError('Dataset not found.', 404),
    )

    renderWithProviders(<AnalyticsPage />)

    await userEvent.selectOptions(await screen.findByLabelText(/dataset/i), 'ds-1')
    await userEvent.type(screen.getByLabelText(/question/i), 'total revenue')
    await userEvent.click(screen.getByRole('button', { name: /^ask$/i }))

    expect(await screen.findByText(/Dataset not found\./)).toBeInTheDocument()
  })

  it('shows an error message when loading datasets fails', async () => {
    vi.mocked(apiClient.listDatasets).mockRejectedValue(new Error('datasets unavailable'))
    renderWithProviders(<AnalyticsPage />)
    expect(await screen.findByText(/datasets unavailable/)).toBeInTheDocument()
  })
})
