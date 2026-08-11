import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { KpiDashboard } from './KpiDashboard'
import * as apiClient from '../../../api/client'

vi.mock('../../../api/client')

const baseSummary = {
  dataset_id: 'abc',
  kpis: [
    { column: 'quantity', kind: 'sum', value: 65 },
    { column: 'quantity', kind: 'average', value: 3.25 },
    { column: 'quantity', kind: 'min', value: 1 },
    { column: 'quantity', kind: 'max', value: 12 },
  ],
  numeric_columns: ['quantity'],
  suggested_breakdown_columns: ['region', 'category'],
  suggested_trend_columns: ['order_date'],
}

describe('KpiDashboard', () => {
  it('renders a stat tile per numeric column with real computed values', async () => {
    vi.mocked(apiClient.getKpiSummary).mockResolvedValue(baseSummary)
    vi.mocked(apiClient.getBreakdown).mockResolvedValue({
      dataset_id: 'abc',
      group_by: 'region',
      metric: 'quantity',
      aggregation: 'sum',
      items: [{ category: 'North', value: 20 }],
      total_categories: 1,
    })
    vi.mocked(apiClient.getTrend).mockResolvedValue({
      dataset_id: 'abc',
      date_column: 'order_date',
      metric: 'quantity',
      granularity: 'month',
      aggregation: 'sum',
      points: [{ period: '2024-01-01', value: 41 }],
    })

    render(<KpiDashboard datasetId="abc" />)

    // "quantity" also appears in the breakdown/trend metric <select> options,
    // so scope to the stat tile's own label element.
    expect(await screen.findByText('quantity', { selector: 'p' })).toBeInTheDocument()
    expect(screen.getByText('65')).toBeInTheDocument() // sum
    expect(screen.getByText('3.25')).toBeInTheDocument() // average
  })

  it('shows an empty state when the dataset has no numeric columns', async () => {
    vi.mocked(apiClient.getKpiSummary).mockResolvedValue({
      ...baseSummary,
      kpis: [],
      numeric_columns: [],
      suggested_breakdown_columns: [],
      suggested_trend_columns: [],
    })

    render(<KpiDashboard datasetId="abc" />)

    expect(await screen.findByText('No KPIs available')).toBeInTheDocument()
  })

  it('shows an error message when the summary request fails', async () => {
    vi.mocked(apiClient.getKpiSummary).mockRejectedValue(new Error('network down'))

    render(<KpiDashboard datasetId="abc" />)

    expect(await screen.findByText(/network down/)).toBeInTheDocument()
  })

  it('shows a "no breakdown available" empty state when there is no candidate column', async () => {
    vi.mocked(apiClient.getKpiSummary).mockResolvedValue({
      ...baseSummary,
      suggested_breakdown_columns: [],
    })

    render(<KpiDashboard datasetId="abc" />)

    expect(await screen.findByText('No breakdown available')).toBeInTheDocument()
    expect(apiClient.getBreakdown).not.toHaveBeenCalled()
  })

  it('shows a "no trend available" empty state when there is no datetime column', async () => {
    vi.mocked(apiClient.getKpiSummary).mockResolvedValue({
      ...baseSummary,
      suggested_trend_columns: [],
    })

    render(<KpiDashboard datasetId="abc" />)

    expect(await screen.findByText('No trend available')).toBeInTheDocument()
    expect(apiClient.getTrend).not.toHaveBeenCalled()
  })

  it('re-fetches the breakdown with the newly selected group-by column', async () => {
    vi.mocked(apiClient.getKpiSummary).mockResolvedValue(baseSummary)
    vi.mocked(apiClient.getBreakdown).mockResolvedValue({
      dataset_id: 'abc',
      group_by: 'region',
      metric: 'quantity',
      aggregation: 'sum',
      items: [{ category: 'North', value: 20 }],
      total_categories: 1,
    })
    vi.mocked(apiClient.getTrend).mockResolvedValue({
      dataset_id: 'abc',
      date_column: 'order_date',
      metric: 'quantity',
      granularity: 'month',
      aggregation: 'sum',
      points: [{ period: '2024-01-01', value: 41 }],
    })

    render(<KpiDashboard datasetId="abc" />)
    await screen.findByText('Breakdown')
    await waitFor(() => expect(apiClient.getBreakdown).toHaveBeenCalledWith('abc', 'region', 'quantity', 'sum'))

    const breakdownSection = screen.getByText('Breakdown').closest('div')!.parentElement!
    const groupBySelect = within(breakdownSection).getByLabelText('Group by')
    await userEvent.selectOptions(groupBySelect, 'category')

    await waitFor(() =>
      expect(apiClient.getBreakdown).toHaveBeenCalledWith('abc', 'category', 'quantity', 'sum'),
    )
  })

  it('omits the metric selector and passes no metric when aggregation is "count"', async () => {
    vi.mocked(apiClient.getKpiSummary).mockResolvedValue(baseSummary)
    vi.mocked(apiClient.getBreakdown).mockResolvedValue({
      dataset_id: 'abc',
      group_by: 'region',
      metric: null,
      aggregation: 'count',
      items: [{ category: 'North', value: 5 }],
      total_categories: 1,
    })
    vi.mocked(apiClient.getTrend).mockResolvedValue({
      dataset_id: 'abc',
      date_column: 'order_date',
      metric: 'quantity',
      granularity: 'month',
      aggregation: 'sum',
      points: [],
    })

    render(<KpiDashboard datasetId="abc" />)
    await screen.findByText('Breakdown')

    const breakdownSection = screen.getByText('Breakdown').closest('div')!.parentElement!
    const aggSelect = within(breakdownSection).getByLabelText('Aggregation')
    await userEvent.selectOptions(aggSelect, 'count')

    expect(within(breakdownSection).queryByLabelText('Metric')).not.toBeInTheDocument()
    await waitFor(() =>
      expect(apiClient.getBreakdown).toHaveBeenCalledWith('abc', 'region', undefined, 'count'),
    )
  })
})
