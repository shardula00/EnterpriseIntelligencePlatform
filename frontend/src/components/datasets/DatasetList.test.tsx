import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DatasetList } from './DatasetList'
import type { DatasetSummary } from '../../api/types'
import * as apiClient from '../../api/client'
import { renderWithProviders } from '../../test/renderWithProviders'
import { fakeUser, setFakeToken, VIEWER_PERMISSIONS } from '../../test/authTestUtils'

vi.mock('../../api/client')

const sample: DatasetSummary = {
  id: 'ds-1',
  name: 'orders_sample',
  original_filename: 'orders_sample.csv',
  file_type: 'csv',
  storage_schema: 'ingested',
  storage_table_name: 'ds_abc',
  row_count: 20,
  column_count: 9,
  quality_score: 100,
  status: 'ready',
  created_at: '2026-01-01T00:00:00Z',
}

beforeEach(() => {
  setFakeToken()
  vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
})

describe('DatasetList', () => {
  it('shows an empty state when there are no datasets', async () => {
    renderWithProviders(<DatasetList datasets={[]} onDelete={vi.fn()} />)
    expect(await screen.findByText('No datasets yet')).toBeInTheDocument()
  })

  it('renders a row per dataset with its real quality score', async () => {
    renderWithProviders(<DatasetList datasets={[sample]} onDelete={vi.fn()} />)

    expect(await screen.findByText('orders_sample')).toBeInTheDocument()
    expect(screen.getByText('20')).toBeInTheDocument()
    expect(screen.getByText(/100\.0/)).toBeInTheDocument()
  })

  it('calls onDelete with the dataset when Delete is clicked (Admin, has dataset:delete)', async () => {
    const onDelete = vi.fn()
    renderWithProviders(<DatasetList datasets={[sample]} onDelete={onDelete} />)

    const deleteButton = await screen.findByRole('button', { name: /delete/i })
    await userEvent.click(deleteButton)

    expect(onDelete).toHaveBeenCalledWith(sample)
  })

  it('hides the Delete button for a Viewer (no dataset:delete permission)', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['VIEWER'], permissions: VIEWER_PERMISSIONS }),
    )

    renderWithProviders(<DatasetList datasets={[sample]} onDelete={vi.fn()} />)

    await screen.findByText('orders_sample')
    expect(screen.queryByRole('button', { name: /delete/i })).not.toBeInTheDocument()
  })
})
