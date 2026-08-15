import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AnalyticsQueryForm } from './AnalyticsQueryForm'
import type { DatasetSummary } from '../../api/types'

const datasets: DatasetSummary[] = [
  {
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
  },
]

describe('AnalyticsQueryForm', () => {
  it('lists every dataset in the select', () => {
    render(
      <AnalyticsQueryForm
        datasets={datasets}
        datasetId={null}
        onDatasetChange={vi.fn()}
        onAsk={vi.fn()}
      />,
    )
    expect(screen.getByRole('option', { name: /phase8_sales/ })).toBeInTheDocument()
  })

  it('calls onDatasetChange when a dataset is selected', async () => {
    const onDatasetChange = vi.fn()
    render(
      <AnalyticsQueryForm
        datasets={datasets}
        datasetId={null}
        onDatasetChange={onDatasetChange}
        onAsk={vi.fn()}
      />,
    )

    await userEvent.selectOptions(screen.getByLabelText(/dataset/i), 'ds-1')
    expect(onDatasetChange).toHaveBeenCalledWith('ds-1')
  })

  it('disables Ask until both a dataset and a question are provided', async () => {
    render(
      <AnalyticsQueryForm
        datasets={datasets}
        datasetId={null}
        onDatasetChange={vi.fn()}
        onAsk={vi.fn()}
      />,
    )
    expect(screen.getByRole('button', { name: /^ask$/i })).toBeDisabled()

    await userEvent.type(screen.getByLabelText(/question/i), 'total revenue')
    expect(screen.getByRole('button', { name: /^ask$/i })).toBeDisabled()
  })

  it('calls onAsk with the trimmed question once a dataset is selected', async () => {
    const onAsk = vi.fn()
    render(
      <AnalyticsQueryForm
        datasets={datasets}
        datasetId="ds-1"
        onDatasetChange={vi.fn()}
        onAsk={onAsk}
      />,
    )

    await userEvent.type(screen.getByLabelText(/question/i), '  total revenue  ')
    await userEvent.click(screen.getByRole('button', { name: /^ask$/i }))

    expect(onAsk).toHaveBeenCalledWith('total revenue')
  })

  it('disables the input and button while a question is in flight', () => {
    render(
      <AnalyticsQueryForm
        datasets={datasets}
        datasetId="ds-1"
        onDatasetChange={vi.fn()}
        onAsk={vi.fn()}
        disabled
      />,
    )
    expect(screen.getByLabelText(/question/i)).toBeDisabled()
    expect(screen.getByRole('button', { name: /asking/i })).toBeDisabled()
  })
})
