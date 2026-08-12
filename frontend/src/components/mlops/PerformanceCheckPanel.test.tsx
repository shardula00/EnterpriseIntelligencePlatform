import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PerformanceCheckPanel } from './PerformanceCheckPanel'
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

describe('PerformanceCheckPanel', () => {
  it('runs a real performance check and shows the real baseline/current comparison', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
    )
    vi.mocked(apiClient.runPerformanceCheck).mockResolvedValue({
      model_version_id: 'version-1',
      dataset_id: 'ds-1',
      task_type: 'classification',
      ground_truth_available: true,
      primary_metric: 'roc_auc',
      baseline_value: 0.81,
      current_value: 0.49,
      absolute_change: -0.32,
      relative_change: -0.395,
      warning_threshold: 0.05,
      severe_threshold: 0.15,
      status: 'degraded',
      explanation: 'roc_auc dropped from 0.81 to 0.49.',
      extra_metrics: { accuracy: 0.5 },
    })

    renderWithProviders(<PerformanceCheckPanel versionId="version-1" />)

    const select = await screen.findByLabelText('Evaluate against dataset')
    await userEvent.selectOptions(select, 'ds-1')
    await userEvent.click(screen.getByRole('button', { name: 'Run performance check' }))

    expect(apiClient.runPerformanceCheck).toHaveBeenCalledWith('version-1', 'ds-1')
    expect(await screen.findByText('degraded')).toBeInTheDocument()
    expect(screen.getByText('baseline: 0.81')).toBeInTheDocument()
    expect(screen.getByText('current: 0.49')).toBeInTheDocument()
    expect(screen.getByText('roc_auc dropped from 0.81 to 0.49.')).toBeInTheDocument()
    expect(screen.getByText(/accuracy/)).toBeInTheDocument()
  })

  it('flags a proxy-signal check with no ground truth distinctly', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
    )
    vi.mocked(apiClient.runPerformanceCheck).mockResolvedValue({
      model_version_id: 'version-1',
      dataset_id: 'ds-1',
      task_type: 'anomaly_detection',
      ground_truth_available: false,
      primary_metric: 'anomaly_percentage',
      baseline_value: 5.0,
      current_value: 40.0,
      absolute_change: 35.0,
      relative_change: 7.0,
      warning_threshold: 0.05,
      severe_threshold: 0.15,
      status: 'degraded',
      explanation: 'Anomaly detection has no ground truth - proxy signal only.',
      extra_metrics: {},
    })

    renderWithProviders(<PerformanceCheckPanel versionId="version-1" />)
    await userEvent.selectOptions(await screen.findByLabelText('Evaluate against dataset'), 'ds-1')
    await userEvent.click(screen.getByRole('button', { name: 'Run performance check' }))

    expect(await screen.findByText('No ground truth - proxy signal only')).toBeInTheDocument()
  })

  it('calls onChecked after a successful run, so a parent can refresh its own event list', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
    )
    vi.mocked(apiClient.runPerformanceCheck).mockResolvedValue({
      model_version_id: 'version-1',
      dataset_id: 'ds-1',
      task_type: 'classification',
      ground_truth_available: true,
      primary_metric: 'roc_auc',
      baseline_value: 0.81,
      current_value: 0.8,
      absolute_change: -0.01,
      relative_change: -0.012,
      warning_threshold: 0.05,
      severe_threshold: 0.15,
      status: 'stable',
      explanation: 'roc_auc is stable at 0.8.',
      extra_metrics: {},
    })
    const onChecked = vi.fn()

    renderWithProviders(<PerformanceCheckPanel versionId="version-1" onChecked={onChecked} />)
    await userEvent.selectOptions(await screen.findByLabelText('Evaluate against dataset'), 'ds-1')
    await userEvent.click(screen.getByRole('button', { name: 'Run performance check' }))

    await screen.findByText('roc_auc is stable at 0.8.')
    expect(onChecked).toHaveBeenCalledTimes(1)
  })

  it('shows an access message instead of a form for a Viewer (no mlops:evaluate)', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['VIEWER'], permissions: VIEWER_PERMISSIONS }),
    )

    renderWithProviders(<PerformanceCheckPanel versionId="version-1" />)

    expect(
      await screen.findByText(/Running a performance check requires Analyst or Admin access/),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Run performance check' })).not.toBeInTheDocument()
  })
})
