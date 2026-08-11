import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { SegmentationConfigForm } from './SegmentationConfigForm'
import * as apiClient from '../../api/client'
import { renderWithProviders } from '../../test/renderWithProviders'
import { fakeUser, setFakeToken } from '../../test/authTestUtils'

vi.mock('../../api/client')

const check = {
  task_type: 'segmentation' as const,
  suitable: true,
  reasons: [],
  suggested_target_columns: [],
  suggested_datetime_columns: [],
  suggested_feature_columns: ['income', 'spend'],
}

beforeEach(() => {
  setFakeToken()
  vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
})

describe('SegmentationConfigForm', () => {
  it('pre-fills suggested feature columns and a default of 4 clusters', () => {
    renderWithProviders(
      <SegmentationConfigForm
        datasetId="ds-1"
        columns={['income', 'spend', 'purchase_frequency']}
        check={check}
        onTrained={vi.fn()}
      />,
    )

    expect(screen.getByRole('checkbox', { name: 'income' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'spend' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'purchase_frequency' })).not.toBeChecked()
    expect(screen.getByText('Number of clusters (4)')).toBeInTheDocument()
  })

  it('submits the chosen features and cluster count', async () => {
    vi.mocked(apiClient.trainSegmentation).mockResolvedValue({ run: { id: 'run-9' } } as never)
    const onTrained = vi.fn()

    renderWithProviders(
      <SegmentationConfigForm
        datasetId="ds-1"
        columns={['income', 'spend', 'purchase_frequency']}
        check={check}
        onTrained={onTrained}
      />,
    )

    await userEvent.click(screen.getByRole('checkbox', { name: 'purchase_frequency' }))
    await userEvent.click(screen.getByRole('button', { name: 'Train model' }))

    expect(apiClient.trainSegmentation).toHaveBeenCalledWith({
      datasetId: 'ds-1',
      featureColumns: ['income', 'spend', 'purchase_frequency'],
      nClusters: 4,
    })
    expect(onTrained).toHaveBeenCalledWith('run-9')
  })

  it('disables submit when fewer than 2 feature columns are selected', async () => {
    renderWithProviders(
      <SegmentationConfigForm
        datasetId="ds-1"
        columns={['income', 'spend']}
        check={check}
        onTrained={vi.fn()}
      />,
    )

    await userEvent.click(screen.getByRole('checkbox', { name: 'spend' })) // uncheck -> only income left

    expect(screen.getByRole('button', { name: 'Train model' })).toBeDisabled()
  })

  it('shows the real backend error when training fails', async () => {
    vi.mocked(apiClient.trainSegmentation).mockRejectedValue(
      new Error('n_clusters (5) must be smaller than the number of rows (3).'),
    )

    renderWithProviders(
      <SegmentationConfigForm
        datasetId="ds-1"
        columns={['income', 'spend']}
        check={check}
        onTrained={vi.fn()}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Train model' }))

    expect(await screen.findByText(/must be smaller than the number of rows/)).toBeInTheDocument()
  })
})
