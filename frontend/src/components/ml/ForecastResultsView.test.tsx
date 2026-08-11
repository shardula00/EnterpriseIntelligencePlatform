import { fireEvent, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ForecastResultsView } from './ForecastResultsView'
import type { ForecastResults } from '../../api/types'
import * as apiClient from '../../api/client'
import { renderWithProviders } from '../../test/renderWithProviders'
import { ANALYST_PERMISSIONS, fakeUser, setFakeToken } from '../../test/authTestUtils'

vi.mock('../../api/client')

const resultsWithInterval: ForecastResults = {
  datetime_column: 'order_date',
  target_column: 'sales_amount',
  horizon: 14,
  candidate_models: [
    { model_name: 'Naive', metrics: { mae: 30, rmse: 35 } },
    { model_name: 'Random Forest', metrics: { mae: 12, rmse: 15 } },
  ],
  selected_model: 'Random Forest',
  primary_metric: 'mae',
  metrics: { mae: 12, rmse: 15 },
  historical: [
    { period: '2024-01-01', value: 100 },
    { period: '2024-01-02', value: 110 },
  ],
  forecast: [{ period: '2024-01-15', value: 120, lower: 100, upper: 140 }],
  has_confidence_interval: true,
  random_seed: 42,
}

beforeEach(() => {
  setFakeToken()
  vi.mocked(apiClient.authMe).mockResolvedValue(
    fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
  )
})

describe('ForecastResultsView', () => {
  it('highlights the selected model and never claims a confidence interval label is missing when one exists', () => {
    renderWithProviders(<ForecastResultsView runId="run-1" results={resultsWithInterval} />)

    expect(screen.getByText('Selected')).toBeInTheDocument()
    expect(screen.queryByText(/No confidence interval is shown/)).not.toBeInTheDocument()
  })

  it('explains the absence of a confidence interval when the selected model does not produce one', () => {
    const resultsWithoutInterval: ForecastResults = {
      ...resultsWithInterval,
      selected_model: 'Naive',
      has_confidence_interval: false,
      forecast: [{ period: '2024-01-15', value: 105, lower: null, upper: null }],
    }

    renderWithProviders(<ForecastResultsView runId="run-1" results={resultsWithoutInterval} />)

    expect(screen.getByText(/doesn't produce one/)).toBeInTheDocument()
  })

  it('lets the user change the horizon and requests that exact horizon when predicting', async () => {
    vi.mocked(apiClient.predictMlRun).mockResolvedValue({
      run_id: 'run-1',
      task_type: 'forecasting',
      predictions: [{ period: '2024-01-20', value: 130, lower: null, upper: null }],
      summary: { horizon: 30 },
    } as never)

    renderWithProviders(<ForecastResultsView runId="run-1" results={resultsWithInterval} />)

    fireEvent.change(screen.getByRole('slider'), { target: { value: '30' } })

    const button = await screen.findByRole('button', { name: /Forecast next \d+ periods/ })
    await userEvent.click(button)

    expect(apiClient.predictMlRun).toHaveBeenCalledWith('run-1', 30)
  })
})
