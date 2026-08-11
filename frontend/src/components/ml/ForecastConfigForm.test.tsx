import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ForecastConfigForm } from './ForecastConfigForm'
import * as apiClient from '../../api/client'
import { renderWithProviders } from '../../test/renderWithProviders'
import { fakeUser, setFakeToken } from '../../test/authTestUtils'

vi.mock('../../api/client')

const check = {
  task_type: 'forecasting' as const,
  suitable: true,
  reasons: [],
  suggested_target_columns: ['sales_amount'],
  suggested_datetime_columns: ['order_date'],
  suggested_feature_columns: [],
}

beforeEach(() => {
  setFakeToken()
  vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
})

describe('ForecastConfigForm', () => {
  it('pre-fills datetime/target columns and a default 14-period horizon', () => {
    renderWithProviders(<ForecastConfigForm datasetId="ds-1" check={check} onTrained={vi.fn()} />)

    expect(screen.getByRole('combobox', { name: 'Datetime column' })).toHaveValue('order_date')
    expect(screen.getByRole('combobox', { name: 'Target column (numeric)' })).toHaveValue(
      'sales_amount',
    )
    expect(screen.getByText('Forecast horizon (14 periods)')).toBeInTheDocument()
  })

  it('submits the chosen horizon and navigates via onTrained on success', async () => {
    vi.mocked(apiClient.trainForecasting).mockResolvedValue({ run: { id: 'run-7' } } as never)
    const onTrained = vi.fn()

    renderWithProviders(<ForecastConfigForm datasetId="ds-1" check={check} onTrained={onTrained} />)
    await userEvent.click(screen.getByRole('button', { name: 'Train model' }))

    expect(apiClient.trainForecasting).toHaveBeenCalledWith({
      datasetId: 'ds-1',
      datetimeColumn: 'order_date',
      targetColumn: 'sales_amount',
      horizon: 14,
    })
    expect(onTrained).toHaveBeenCalledWith('run-7')
  })

  it('shows the real backend error when training fails', async () => {
    vi.mocked(apiClient.trainForecasting).mockRejectedValue(
      new Error('Not enough history for a horizon of 14 periods.'),
    )

    renderWithProviders(<ForecastConfigForm datasetId="ds-1" check={check} onTrained={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: 'Train model' }))

    expect(await screen.findByText(/Not enough history/)).toBeInTheDocument()
  })
})
