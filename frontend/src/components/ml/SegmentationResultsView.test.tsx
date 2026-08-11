import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { SegmentationResultsView } from './SegmentationResultsView'
import type { SegmentationResults } from '../../api/types'
import * as apiClient from '../../api/client'
import { renderWithProviders } from '../../test/renderWithProviders'
import { ANALYST_PERMISSIONS, fakeUser, setFakeToken } from '../../test/authTestUtils'

vi.mock('../../api/client')

const results: SegmentationResults = {
  feature_columns: ['income', 'spend'],
  n_clusters: 2,
  silhouette_score: 0.82,
  cluster_sizes: { '0': 40, '1': 60 },
  cluster_profiles: [
    { cluster: 0, size: 40, feature_means: { income: 105.2, spend: 20.1 } },
    { cluster: 1, size: 60, feature_means: { income: 26.5, spend: 79.8 } },
  ],
  cluster_centers: [
    [105.2, 20.1],
    [26.5, 79.8],
  ],
  random_seed: 42,
  was_sampled: false,
}

beforeEach(() => {
  setFakeToken()
  vi.mocked(apiClient.authMe).mockResolvedValue(
    fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
  )
})

describe('SegmentationResultsView', () => {
  it('shows the real silhouette score and cluster count', () => {
    renderWithProviders(<SegmentationResultsView runId="run-1" results={results} />)

    expect(screen.getByText('0.82')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('renders one profile row per cluster with its real feature means and size', () => {
    renderWithProviders(<SegmentationResultsView runId="run-1" results={results} />)

    const cluster0Row = screen.getByText('Cluster 0').closest('tr')!
    expect(cluster0Row).toHaveTextContent('40')
    expect(cluster0Row).toHaveTextContent('105.2')
    expect(cluster0Row).toHaveTextContent('20.1')

    const cluster1Row = screen.getByText('Cluster 1').closest('tr')!
    expect(cluster1Row).toHaveTextContent('60')
    expect(cluster1Row).toHaveTextContent('26.5')
  })

  it('assigns real predicted clusters when the predict action is run', async () => {
    vi.mocked(apiClient.predictMlRun).mockResolvedValue({
      run_id: 'run-1',
      task_type: 'segmentation',
      predictions: [],
      summary: { row_count: 300 },
    } as never)

    renderWithProviders(<SegmentationResultsView runId="run-1" results={results} />)
    await userEvent.click(await screen.findByRole('button', { name: 'Run predictions' }))

    expect(apiClient.predictMlRun).toHaveBeenCalledWith('run-1', undefined)
    expect(await screen.findByText(/Assigned 300 rows to 2 clusters/)).toBeInTheDocument()
  })
})
