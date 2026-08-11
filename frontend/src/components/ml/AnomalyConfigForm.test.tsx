import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AnomalyConfigForm } from './AnomalyConfigForm'
import * as apiClient from '../../api/client'
import { renderWithProviders } from '../../test/renderWithProviders'
import { fakeUser, setFakeToken } from '../../test/authTestUtils'

vi.mock('../../api/client')

const check = {
  task_type: 'anomaly_detection' as const,
  suitable: true,
  reasons: [],
  suggested_target_columns: [],
  suggested_datetime_columns: [],
  suggested_feature_columns: ['amount', 'distance_from_home_km'],
}

beforeEach(() => {
  setFakeToken()
  vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
})

describe('AnomalyConfigForm', () => {
  it('pre-fills suggested feature columns and a default 5% contamination rate', () => {
    renderWithProviders(
      <AnomalyConfigForm
        datasetId="ds-1"
        columns={['amount', 'distance_from_home_km', 'transaction_hour']}
        check={check}
        onTrained={vi.fn()}
      />,
    )

    expect(screen.getByRole('checkbox', { name: 'amount' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'distance_from_home_km' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'transaction_hour' })).not.toBeChecked()
    expect(screen.getByText('Expected anomaly rate (5%)')).toBeInTheDocument()
  })

  it('submits the chosen features and contamination rate', async () => {
    vi.mocked(apiClient.trainAnomalyDetection).mockResolvedValue({ run: { id: 'run-3' } } as never)
    const onTrained = vi.fn()

    renderWithProviders(
      <AnomalyConfigForm
        datasetId="ds-1"
        columns={['amount', 'distance_from_home_km']}
        check={check}
        onTrained={onTrained}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Train model' }))

    expect(apiClient.trainAnomalyDetection).toHaveBeenCalledWith({
      datasetId: 'ds-1',
      featureColumns: ['amount', 'distance_from_home_km'],
      contamination: 0.05,
    })
    expect(onTrained).toHaveBeenCalledWith('run-3')
  })

  it('disables submit when no feature columns are selected', async () => {
    renderWithProviders(
      <AnomalyConfigForm
        datasetId="ds-1"
        columns={['amount', 'distance_from_home_km']}
        check={check}
        onTrained={vi.fn()}
      />,
    )

    await userEvent.click(screen.getByRole('checkbox', { name: 'amount' }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'distance_from_home_km' }))

    expect(screen.getByRole('button', { name: 'Train model' })).toBeDisabled()
  })

  it('shows the real backend error when training fails', async () => {
    vi.mocked(apiClient.trainAnomalyDetection).mockRejectedValue(
      new Error('At least 1 usable feature column is required after removing constant columns.'),
    )

    renderWithProviders(
      <AnomalyConfigForm
        datasetId="ds-1"
        columns={['amount', 'distance_from_home_km']}
        check={check}
        onTrained={vi.fn()}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Train model' }))

    expect(await screen.findByText(/usable feature column is required/)).toBeInTheDocument()
  })
})
