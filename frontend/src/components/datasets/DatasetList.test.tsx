import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { DatasetList } from './DatasetList'
import type { DatasetSummary } from '../../api/types'

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

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('DatasetList', () => {
  it('shows an empty state when there are no datasets', () => {
    renderWithRouter(<DatasetList datasets={[]} onDelete={vi.fn()} />)
    expect(screen.getByText('No datasets yet')).toBeInTheDocument()
  })

  it('renders a row per dataset with its real quality score', () => {
    renderWithRouter(<DatasetList datasets={[sample]} onDelete={vi.fn()} />)

    expect(screen.getByText('orders_sample')).toBeInTheDocument()
    expect(screen.getByText('20')).toBeInTheDocument()
    expect(screen.getByText(/100\.0/)).toBeInTheDocument()
  })

  it('calls onDelete with the dataset when Delete is clicked', async () => {
    const onDelete = vi.fn()
    renderWithRouter(<DatasetList datasets={[sample]} onDelete={onDelete} />)

    await userEvent.click(screen.getByRole('button', { name: /delete/i }))

    expect(onDelete).toHaveBeenCalledWith(sample)
  })
})
