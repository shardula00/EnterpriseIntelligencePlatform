import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MlRunPage } from './MlRunPage'
import * as apiClient from '../../api/client'
import { AuthProvider } from '../../auth/AuthContext'
import { fakeUser, setFakeToken } from '../../test/authTestUtils'

vi.mock('../../api/client')

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/ml/runs/run-1']}>
      <AuthProvider>
        <Routes>
          <Route path="/ml/runs/:runId" element={<MlRunPage />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  setFakeToken()
  vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
})

const baseRun = {
  id: 'run-1',
  dataset_id: 'ds-1',
  model_name: 'Logistic Regression',
  status: 'completed',
  configuration: {},
  created_by: null,
  created_at: '2026-01-01T00:00:00Z',
  completed_at: '2026-01-01T00:00:01Z',
}

describe('MlRunPage', () => {
  it('dispatches a classification run to the classification results view', async () => {
    vi.mocked(apiClient.getMlRun).mockResolvedValue({
      run: { ...baseRun, task_type: 'classification' },
      results: {
        target_column: 'churned',
        feature_columns: ['tenure_months'],
        class_distribution: { True: 10, False: 20 },
        candidate_models: [{ model_name: 'Logistic Regression', metrics: { roc_auc: 0.9 } }],
        selected_model: 'Logistic Regression',
        primary_metric: 'roc_auc',
        primary_metric_rationale: 'Because imbalance.',
        metrics: { roc_auc: 0.9 },
        confusion_matrix: { labels: ['False', 'True'], matrix: [[18, 2], [1, 9]] },
        feature_importance: [{ feature: 'tenure_months', importance: 0.5, direction: 'negative' }],
        sample_predictions: [],
        test_size: 0.25,
        random_seed: 42,
        was_sampled: false,
      },
    } as never)

    renderPage()

    expect(await screen.findByRole('heading', { name: 'Binary Classification' })).toBeInTheDocument()
    expect(screen.getByText('Model comparison')).toBeInTheDocument()
    expect(screen.getByText('Because imbalance.')).toBeInTheDocument()
  })

  it('dispatches a forecasting run to the forecast results view', async () => {
    vi.mocked(apiClient.getMlRun).mockResolvedValue({
      run: { ...baseRun, task_type: 'forecasting', model_name: 'Random Forest' },
      results: {
        datetime_column: 'order_date',
        target_column: 'sales_amount',
        horizon: 14,
        candidate_models: [{ model_name: 'Naive', metrics: { mae: 20 } }],
        selected_model: 'Random Forest',
        primary_metric: 'mae',
        metrics: { mae: 12 },
        historical: [{ period: '2024-01-01', value: 100 }],
        forecast: [{ period: '2024-01-15', value: 110, lower: 100, upper: 120 }],
        has_confidence_interval: true,
        random_seed: 42,
      },
    } as never)

    renderPage()

    expect(await screen.findByRole('heading', { name: 'Time-Series Forecasting' })).toBeInTheDocument()
    expect(screen.getByText(/Historical values & 14-period forecast/)).toBeInTheDocument()
  })

  it('dispatches a segmentation run to the segmentation results view', async () => {
    vi.mocked(apiClient.getMlRun).mockResolvedValue({
      run: { ...baseRun, task_type: 'segmentation', model_name: 'K-Means' },
      results: {
        feature_columns: ['income', 'spend'],
        n_clusters: 2,
        silhouette_score: 0.8,
        cluster_sizes: { '0': 40, '1': 40 },
        cluster_profiles: [
          { cluster: 0, size: 40, feature_means: { income: 100, spend: 20 } },
          { cluster: 1, size: 40, feature_means: { income: 25, spend: 80 } },
        ],
        cluster_centers: [
          [100, 20],
          [25, 80],
        ],
        random_seed: 42,
        was_sampled: false,
      },
    } as never)

    renderPage()

    expect(await screen.findByRole('heading', { name: 'Customer Segmentation' })).toBeInTheDocument()
    expect(screen.getByText('0.8')).toBeInTheDocument()
  })

  it('dispatches an anomaly_detection run to the anomaly results view', async () => {
    vi.mocked(apiClient.getMlRun).mockResolvedValue({
      run: { ...baseRun, task_type: 'anomaly_detection', model_name: 'Isolation Forest' },
      results: {
        feature_columns: ['amount'],
        contamination: 0.05,
        anomaly_count: 5,
        anomaly_percentage: 5,
        anomalous_records: [{ row_index: 3, anomaly_score: 0.9, is_anomaly: true, values: { amount: 900 } }],
        score_summary: { min: -0.1, max: 0.9, mean: 0.1 },
        random_seed: 42,
        was_sampled: false,
      },
    } as never)

    renderPage()

    expect(await screen.findByRole('heading', { name: 'Anomaly Detection' })).toBeInTheDocument()
    expect(screen.getByText(/5 \(5%\)/)).toBeInTheDocument()
  })

  it('shows an error message when the run fails to load', async () => {
    vi.mocked(apiClient.getMlRun).mockRejectedValue(new Error('ML run not found.'))

    renderPage()

    expect(await screen.findByText(/ML run not found/)).toBeInTheDocument()
  })
})
