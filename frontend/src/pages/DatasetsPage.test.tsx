import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DatasetsPage } from './DatasetsPage'
import * as apiClient from '../api/client'
import { renderWithProviders } from '../test/renderWithProviders'
import { ANALYST_PERMISSIONS, fakeUser, setFakeToken } from '../test/authTestUtils'
import type { DatasetDetail, DatasetSummary } from '../api/types'

// Phase 12: this page had zero test coverage despite existing since Phase 3
// (upload -> list -> delete is one of the most-used flows in the app) - a
// gap surfaced by the new `npm run test:coverage` instrumentation, not a
// new feature. See SECURITY.md's coverage section.
vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client')
  return { ...actual, authMe: vi.fn(), listDatasets: vi.fn(), uploadDataset: vi.fn(), deleteDataset: vi.fn() }
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

beforeEach(() => {
  setFakeToken()
  vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser()) // ADMIN: has dataset:delete
})

describe('DatasetsPage', () => {
  it('shows an empty state when there are no datasets yet', async () => {
    vi.mocked(apiClient.listDatasets).mockResolvedValue([])
    renderWithProviders(<DatasetsPage />)
    expect(await screen.findByText('No datasets yet')).toBeInTheDocument()
    // The upload form is always available, even with nothing uploaded yet.
    expect(screen.getByRole('form', { name: /upload dataset/i })).toBeInTheDocument()
  })

  it('lists uploaded datasets with their quality/row/column info', async () => {
    vi.mocked(apiClient.listDatasets).mockResolvedValue([dataset])
    renderWithProviders(<DatasetsPage />)

    expect(await screen.findByText('phase8_sales')).toBeInTheDocument()
    expect(screen.getByText('28')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'phase8_sales' })).toHaveAttribute(
      'href',
      '/datasets/ds-1',
    )
  })

  it('uploads a file and refreshes the dataset list', async () => {
    vi.mocked(apiClient.listDatasets).mockResolvedValueOnce([]).mockResolvedValueOnce([dataset])
    vi.mocked(apiClient.uploadDataset).mockResolvedValue({
      ...dataset,
      columns: [],
    } as unknown as DatasetDetail)

    renderWithProviders(<DatasetsPage />)
    await screen.findByText('No datasets yet')

    const file = new File(['a,b\n1,2'], 'phase8_sales.csv', { type: 'text/csv' })
    const input = screen.getByLabelText(/file/i) as HTMLInputElement
    await userEvent.upload(input, file)
    await userEvent.click(screen.getByRole('button', { name: /^upload$/i }))

    expect(apiClient.uploadDataset).toHaveBeenCalledWith(file, undefined)
    expect(await screen.findByText('phase8_sales')).toBeInTheDocument()
  })

  it('deletes a dataset (Admin has dataset:delete) and refreshes the list', async () => {
    vi.mocked(apiClient.listDatasets).mockResolvedValueOnce([dataset]).mockResolvedValueOnce([])
    vi.mocked(apiClient.deleteDataset).mockResolvedValue(undefined)

    renderWithProviders(<DatasetsPage />)
    await screen.findByText('phase8_sales')

    await userEvent.click(screen.getByRole('button', { name: /delete/i }))

    expect(apiClient.deleteDataset).toHaveBeenCalledWith('ds-1')
    await waitFor(() => expect(screen.getByText('No datasets yet')).toBeInTheDocument())
  })

  it('hides the Delete control for a user without dataset:delete', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
    )
    vi.mocked(apiClient.listDatasets).mockResolvedValue([dataset])

    renderWithProviders(<DatasetsPage />)

    await screen.findByText('phase8_sales')
    expect(screen.queryByRole('button', { name: /delete/i })).not.toBeInTheDocument()
  })

  it('shows an error message when loading datasets fails', async () => {
    vi.mocked(apiClient.listDatasets).mockRejectedValue(new Error('datasets unavailable'))
    renderWithProviders(<DatasetsPage />)
    expect(await screen.findByText(/datasets unavailable/)).toBeInTheDocument()
  })
})
