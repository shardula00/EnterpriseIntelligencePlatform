import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DriftCheckPanel } from './DriftCheckPanel'
import * as apiClient from '../../api/client'
import { renderWithProviders } from '../../test/renderWithProviders'
import { ANALYST_PERMISSIONS, fakeUser, setFakeToken, VIEWER_PERMISSIONS } from '../../test/authTestUtils'

vi.mock('../../api/client')

const datasets = [
  { id: 'ds-1', name: 'Churn dataset', original_filename: 'a.csv', file_type: 'csv', row_count: 500, column_count: 7, quality_score: 100, status: 'ready', created_at: '2026-01-01T00:00:00Z' },
]

beforeEach(() => {
  setFakeToken()
  vi.mocked(apiClient.listDatasets).mockResolvedValue(datasets as never)
})

describe('DriftCheckPanel', () => {
  it('runs a real drift check and renders the real per-feature results', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
    )
    vi.mocked(apiClient.runDriftCheck).mockResolvedValue({
      model_version_id: 'version-1',
      dataset_id: 'ds-1',
      overall_status: 'drift',
      total_features_checked: 2,
      drifted_feature_count: 1,
      warning_feature_count: 0,
      warning_threshold: 0.1,
      severe_threshold: 0.25,
      features: [
        {
          feature: 'tenure_months', feature_type: 'numeric', method: 'psi', statistic: 2.7,
          status: 'drift', baseline_summary: {}, current_summary: {},
          explanation: 'PSI=2.7 across 10 baseline-quantile bins.',
        },
        {
          feature: 'contract_type', feature_type: 'categorical', method: 'psi', statistic: 0.02,
          status: 'stable', baseline_summary: {}, current_summary: {},
          explanation: 'PSI=0.02 across 3 categories.',
        },
      ],
      explanation: '1 of 2 feature(s) show significant drift.',
    })

    renderWithProviders(<DriftCheckPanel versionId="version-1" />)

    const select = await screen.findByLabelText('Compare against dataset')
    await userEvent.selectOptions(select, 'ds-1')
    await userEvent.click(screen.getByRole('button', { name: 'Run drift check' }))

    expect(apiClient.runDriftCheck).toHaveBeenCalledWith('version-1', 'ds-1')
    await screen.findByText('1 of 2 feature(s) show significant drift.')
    // "drift" appears twice: the overall status badge and tenure_months's
    // own per-feature status badge - both being present is the real assertion.
    expect(screen.getAllByText('drift').length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('tenure_months')).toBeInTheDocument()
    expect(screen.getByText('2.7')).toBeInTheDocument()
    expect(screen.getByText('contract_type')).toBeInTheDocument()
  })

  it('calls onChecked after a successful run, so a parent can refresh its own event list', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
    )
    vi.mocked(apiClient.runDriftCheck).mockResolvedValue({
      model_version_id: 'version-1',
      dataset_id: 'ds-1',
      overall_status: 'stable',
      total_features_checked: 1,
      drifted_feature_count: 0,
      warning_feature_count: 0,
      warning_threshold: 0.1,
      severe_threshold: 0.25,
      features: [],
      explanation: 'No features show significant drift.',
    })
    const onChecked = vi.fn()

    renderWithProviders(<DriftCheckPanel versionId="version-1" onChecked={onChecked} />)
    await userEvent.selectOptions(await screen.findByLabelText('Compare against dataset'), 'ds-1')
    await userEvent.click(screen.getByRole('button', { name: 'Run drift check' }))

    await screen.findByText('No features show significant drift.')
    expect(onChecked).toHaveBeenCalledTimes(1)
  })

  it('disables the run button until a dataset is selected', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
    )

    renderWithProviders(<DriftCheckPanel versionId="version-1" />)
    await screen.findByLabelText('Compare against dataset')

    expect(screen.getByRole('button', { name: 'Run drift check' })).toBeDisabled()
  })

  it('shows an access message instead of a form for a Viewer (no mlops:evaluate)', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['VIEWER'], permissions: VIEWER_PERMISSIONS }),
    )

    renderWithProviders(<DriftCheckPanel versionId="version-1" />)

    expect(
      await screen.findByText(/Running a drift check requires Analyst or Admin access/),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Run drift check' })).not.toBeInTheDocument()
  })
})
