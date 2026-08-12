import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ModelVersionDetailPage } from './ModelVersionDetailPage'
import * as apiClient from '../../api/client'
import { AuthProvider } from '../../auth/AuthContext'
import { ANALYST_PERMISSIONS, fakeUser, setFakeToken } from '../../test/authTestUtils'

vi.mock('../../api/client')

function baseVersion(status: 'candidate' | 'staging' | 'production' | 'archived') {
  return {
    id: 'version-1',
    ml_run_id: 'run-1',
    dataset_id: 'ds-1',
    task_type: 'classification' as const,
    model_name: 'Logistic Regression',
    version_number: 1,
    status,
    artifact_checksum: 'abcdef0123456789',
    created_by: null,
    created_at: '2026-01-01T00:00:00Z',
    promoted_by: null,
    promoted_at: status === 'candidate' ? null : '2026-01-02T00:00:00Z',
  }
}

const runResults = {
  run: {
    id: 'run-1',
    dataset_id: 'ds-1',
    task_type: 'classification' as const,
    model_name: 'Logistic Regression',
    status: 'completed',
    configuration: {},
    created_by: null,
    created_at: '2026-01-01T00:00:00Z',
    completed_at: '2026-01-01T00:00:01Z',
  },
  results: {
    target_column: 'churned',
    feature_columns: ['tenure_months'],
    class_distribution: { False: 60, True: 40 },
    candidate_models: [{ model_name: 'Logistic Regression', metrics: { roc_auc: 0.9 } }],
    selected_model: 'Logistic Regression',
    primary_metric: 'roc_auc',
    primary_metric_rationale: 'ROC-AUC handles imbalance.',
    metrics: { roc_auc: 0.9 },
    confusion_matrix: { labels: ['False', 'True'], matrix: [[55, 5], [8, 32]] },
    feature_importance: [{ feature: 'tenure_months', importance: 0.5, direction: 'negative' }],
    sample_predictions: [],
    test_size: 0.25,
    random_seed: 42,
    was_sampled: false,
  },
}

function renderPage(version: ReturnType<typeof baseVersion>) {
  vi.mocked(apiClient.getModelVersion).mockResolvedValue({ version, run: runResults } as never)
  vi.mocked(apiClient.listMonitoringEvents).mockResolvedValue([])
  vi.mocked(apiClient.listDatasets).mockResolvedValue([])

  return render(
    <MemoryRouter initialEntries={['/mlops/versions/version-1']}>
      <AuthProvider>
        <Routes>
          <Route path="/mlops/versions/:versionId" element={<ModelVersionDetailPage />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  setFakeToken()
})

describe('ModelVersionDetailPage', () => {
  it('shows real version info and reuses the Phase 5 results view for the training run', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
    renderPage(baseVersion('candidate'))

    expect(await screen.findByRole('heading', { name: /Binary Classification - v1/ })).toBeInTheDocument()
    expect(screen.getByText('Candidate')).toBeInTheDocument()
    expect(screen.getByText(/abcdef01234567/)).toBeInTheDocument()
    // Reused Phase 5 component, proven by its own real content appearing here.
    expect(screen.getByText('Model comparison')).toBeInTheDocument()
    expect(screen.getByText('ROC-AUC handles imbalance.')).toBeInTheDocument()
  })

  it('shows only "promote to staging" for a candidate version (Admin)', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
    renderPage(baseVersion('candidate'))

    await screen.findByText('Candidate')
    expect(screen.getByRole('button', { name: 'Promote to staging' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Promote to production' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Archive' })).toBeInTheDocument()
  })

  it('shows "promote to production" and "archive" for a staging version (Admin)', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
    renderPage(baseVersion('staging'))

    await screen.findByText('Staging')
    expect(screen.getByRole('button', { name: 'Promote to production' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Archive' })).toBeInTheDocument()
  })

  it('shows no promotion actions for an archived version - terminal state', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
    renderPage(baseVersion('archived'))

    await screen.findByText('Archived')
    expect(screen.queryByRole('button', { name: /promote/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Archive' })).not.toBeInTheDocument()
    expect(screen.getByText(/Archived is terminal/)).toBeInTheDocument()
  })

  it('promotes the version and reloads the page on success', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
    renderPage(baseVersion('candidate'))
    await screen.findByText('Candidate')

    vi.mocked(apiClient.getModelVersion).mockResolvedValue({
      version: baseVersion('staging'), run: runResults,
    } as never)
    vi.mocked(apiClient.promoteModelVersion).mockResolvedValue(baseVersion('staging') as never)

    await userEvent.click(screen.getByRole('button', { name: 'Promote to staging' }))

    expect(apiClient.promoteModelVersion).toHaveBeenCalledWith('version-1', 'staging')
    expect(await screen.findByText('Staging')).toBeInTheDocument()
  })

  it('hides lifecycle actions for a non-Admin (no mlops:promote) and shows an access message', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
    )
    renderPage(baseVersion('candidate'))

    await screen.findByText('Candidate')
    expect(screen.queryByRole('button', { name: 'Promote to staging' })).not.toBeInTheDocument()
    expect(
      screen.getByText(/Promoting or archiving a model version requires Admin access/),
    ).toBeInTheDocument()
  })

  it('shows an error message when the version fails to load', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
    vi.mocked(apiClient.getModelVersion).mockRejectedValue(new Error('version not found'))
    vi.mocked(apiClient.listMonitoringEvents).mockResolvedValue([])

    render(
      <MemoryRouter initialEntries={['/mlops/versions/version-1']}>
        <AuthProvider>
          <Routes>
            <Route path="/mlops/versions/:versionId" element={<ModelVersionDetailPage />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    )

    expect(await screen.findByText(/version not found/)).toBeInTheDocument()
  })
})
