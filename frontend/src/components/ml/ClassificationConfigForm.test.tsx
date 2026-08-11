import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ClassificationConfigForm } from './ClassificationConfigForm'
import * as apiClient from '../../api/client'
import { renderWithProviders } from '../../test/renderWithProviders'
import { fakeUser, setFakeToken } from '../../test/authTestUtils'

vi.mock('../../api/client')

const check = {
  task_type: 'classification' as const,
  suitable: true,
  reasons: [],
  suggested_target_columns: ['churned'],
  suggested_datetime_columns: [],
  suggested_feature_columns: ['tenure_months', 'monthly_charges'],
}

beforeEach(() => {
  setFakeToken()
  vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
})

describe('ClassificationConfigForm', () => {
  it('pre-fills the target and feature columns from the suggested suitability check', () => {
    renderWithProviders(
      <ClassificationConfigForm
        datasetId="ds-1"
        columns={['tenure_months', 'monthly_charges', 'contract_type', 'churned']}
        check={check}
        onTrained={vi.fn()}
      />,
    )

    expect(screen.getByRole('combobox')).toHaveValue('churned')
    expect(screen.getByRole('checkbox', { name: 'tenure_months' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'monthly_charges' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'contract_type' })).not.toBeChecked()
    // The target column is never offered as a feature.
    expect(screen.queryByRole('checkbox', { name: 'churned' })).not.toBeInTheDocument()
  })

  it('submits real chosen columns and navigates via onTrained on success', async () => {
    vi.mocked(apiClient.trainClassification).mockResolvedValue({
      run: { id: 'run-42' },
    } as never)
    const onTrained = vi.fn()

    renderWithProviders(
      <ClassificationConfigForm
        datasetId="ds-1"
        columns={['tenure_months', 'monthly_charges', 'contract_type', 'churned']}
        check={check}
        onTrained={onTrained}
      />,
    )

    await userEvent.click(screen.getByRole('checkbox', { name: 'contract_type' }))
    await userEvent.click(screen.getByRole('button', { name: 'Train model' }))

    expect(apiClient.trainClassification).toHaveBeenCalledWith({
      datasetId: 'ds-1',
      targetColumn: 'churned',
      featureColumns: ['tenure_months', 'monthly_charges', 'contract_type'],
      testSize: 0.25,
    })
    expect(onTrained).toHaveBeenCalledWith('run-42')
  })

  it('shows the real backend error and does not call onTrained when training fails', async () => {
    vi.mocked(apiClient.trainClassification).mockRejectedValue(
      new Error('Target column has 3 distinct values, not 2.'),
    )
    const onTrained = vi.fn()

    renderWithProviders(
      <ClassificationConfigForm
        datasetId="ds-1"
        columns={['tenure_months', 'churned']}
        check={check}
        onTrained={onTrained}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: 'Train model' }))

    expect(await screen.findByText(/3 distinct values, not 2/)).toBeInTheDocument()
    expect(onTrained).not.toHaveBeenCalled()
  })

  it('disables submit when no feature columns are selected', async () => {
    renderWithProviders(
      <ClassificationConfigForm
        datasetId="ds-1"
        columns={['tenure_months', 'monthly_charges', 'churned']}
        check={check}
        onTrained={vi.fn()}
      />,
    )

    await userEvent.click(screen.getByRole('checkbox', { name: 'tenure_months' }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'monthly_charges' }))

    expect(screen.getByRole('button', { name: 'Train model' })).toBeDisabled()
  })
})
