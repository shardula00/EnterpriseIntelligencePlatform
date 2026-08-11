import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { DatasetDetailPage } from './DatasetDetailPage'
import * as apiClient from '../api/client'

vi.mock('../api/client')

const dataset = {
  id: 'abc',
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
  columns: [],
}

const columns = [
  {
    position: 0,
    original_name: 'order_id',
    column_name: 'order_id',
    detected_type: 'integer',
    nullable: true,
    null_count: 0,
    distinct_count: 20,
    min_value: '1',
    max_value: '20',
    mean_value: 10.5,
    sample_values: ['1', '2', '3'],
  },
]

const quality = { dataset_id: 'abc', quality_score: 100, issues: [] }
const preview = { dataset_id: 'abc', columns: ['order_id'], rows: [{ order_id: 1 }] }
const lineage = {
  dataset_id: 'abc',
  events: [{ step: 'upload_received', status: 'success', detail: null, created_at: '2026-01-01T00:00:00Z' }],
}
const kpiSummary = {
  dataset_id: 'abc',
  kpis: [],
  numeric_columns: [],
  suggested_breakdown_columns: [],
  suggested_trend_columns: [],
}

function renderPage() {
  vi.mocked(apiClient.getDataset).mockResolvedValue(dataset as never)
  vi.mocked(apiClient.getColumns).mockResolvedValue(columns as never)
  vi.mocked(apiClient.getQuality).mockResolvedValue(quality as never)
  vi.mocked(apiClient.getPreview).mockResolvedValue(preview as never)
  vi.mocked(apiClient.getLineage).mockResolvedValue(lineage as never)
  vi.mocked(apiClient.getKpiSummary).mockResolvedValue(kpiSummary as never)

  return render(
    <MemoryRouter initialEntries={['/datasets/abc']}>
      <Routes>
        <Route path="/datasets/:datasetId" element={<DatasetDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('DatasetDetailPage', () => {
  it('shows the dataset header and defaults to the Overview tab', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { name: 'orders_sample' })).toBeInTheDocument()
    expect(screen.getByText(/20 rows/)).toBeInTheDocument()
    expect(screen.getByText(/9 columns/)).toBeInTheDocument()
    // Overview tab active by default -> KpiDashboard renders its own empty state.
    expect(await screen.findByText('No KPIs available')).toBeInTheDocument()
  })

  it('shows real column data on the Schema tab', async () => {
    renderPage()
    await screen.findByRole('heading', { name: 'orders_sample' })

    await userEvent.click(screen.getByRole('button', { name: 'Schema' }))

    expect(await screen.findByText('order_id')).toBeInTheDocument()
    expect(screen.getByText('Integer')).toBeInTheDocument()
    expect(apiClient.getColumns).toHaveBeenCalledWith('abc')
  })

  it('shows the real quality score and issues on the Quality tab', async () => {
    renderPage()
    await screen.findByRole('heading', { name: 'orders_sample' })

    await userEvent.click(screen.getByRole('button', { name: 'Quality' }))

    expect(await screen.findByText('No quality issues found')).toBeInTheDocument()
    expect(apiClient.getQuality).toHaveBeenCalledWith('abc')
  })

  it('shows real preview rows on the Preview tab', async () => {
    renderPage()
    await screen.findByRole('heading', { name: 'orders_sample' })

    await userEvent.click(screen.getByRole('button', { name: 'Preview' }))

    expect(await screen.findByText('order_id')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(apiClient.getPreview).toHaveBeenCalledWith('abc', 20)
  })

  it('shows real lineage events on the Lineage tab', async () => {
    renderPage()
    await screen.findByRole('heading', { name: 'orders_sample' })

    await userEvent.click(screen.getByRole('button', { name: 'Lineage' }))

    expect(await screen.findByText('Upload received')).toBeInTheDocument()
    expect(apiClient.getLineage).toHaveBeenCalledWith('abc')
  })

  it('shows an error state when the dataset itself fails to load', async () => {
    vi.mocked(apiClient.getDataset).mockRejectedValue(new Error('dataset not found'))

    render(
      <MemoryRouter initialEntries={['/datasets/abc']}>
        <Routes>
          <Route path="/datasets/:datasetId" element={<DatasetDetailPage />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByText(/dataset not found/)).toBeInTheDocument()
  })
})
