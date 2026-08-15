import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AnalyticsResultView } from './AnalyticsResultView'
import type { AnalyticsQueryResult } from '../../api/types'

const answered: AnalyticsQueryResult = {
  id: 'q-1',
  dataset_id: 'ds-1',
  dataset_name: 'phase8_sales',
  question: 'Show total revenue by region.',
  status: 'answered',
  generated_sql: 'SELECT region, sum(ingested.ds_1.revenue) AS revenue FROM ingested.ds_1 GROUP BY region',
  intent: 'breakdown',
  error_message: null,
  columns: ['region', 'revenue'],
  rows: [
    { region: 'West', revenue: 1240000 },
    { region: 'East', revenue: 980000 },
  ],
  row_count: 2,
  created_at: '2026-01-01T00:00:00Z',
}

describe('AnalyticsResultView', () => {
  it('renders the generated SQL and a row per result', () => {
    render(<AnalyticsResultView result={answered} />)

    expect(screen.getByText(/SELECT region/)).toBeInTheDocument()
    expect(screen.getByText('Answered')).toBeInTheDocument()
    expect(screen.getByText('West')).toBeInTheDocument()
    expect(screen.getByText('1,240,000')).toBeInTheDocument()
    expect(screen.getByText('East')).toBeInTheDocument()
  })

  it('renders an empty state when the query ran but returned no rows', () => {
    render(<AnalyticsResultView result={{ ...answered, rows: [], row_count: 0 }} />)
    expect(screen.getByText('No matching rows')).toBeInTheDocument()
  })

  it('renders the explanation, not a table, for an unsupported question', () => {
    render(
      <AnalyticsResultView
        result={{
          ...answered,
          status: 'unsupported',
          generated_sql: null,
          columns: [],
          rows: [],
          row_count: 0,
          error_message: 'Could not identify which numeric column this question is about.',
        }}
      />,
    )

    expect(screen.getByText('Unsupported question')).toBeInTheDocument()
    expect(screen.getByText(/Could not identify which numeric column/)).toBeInTheDocument()
    expect(screen.queryByText(/SELECT/)).not.toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('renders the error explanation for a failed query', () => {
    render(
      <AnalyticsResultView
        result={{
          ...answered,
          status: 'error',
          generated_sql: null,
          error_message: 'The analytics query could not be executed. Please try again.',
        }}
      />,
    )

    expect(screen.getByText('Error')).toBeInTheDocument()
    expect(screen.getByText(/could not be executed/)).toBeInTheDocument()
  })
})
