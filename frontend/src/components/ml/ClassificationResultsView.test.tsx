import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ClassificationResultsView } from './ClassificationResultsView'
import type { ClassificationResults } from '../../api/types'
import * as apiClient from '../../api/client'
import { renderWithProviders } from '../../test/renderWithProviders'
import { ANALYST_PERMISSIONS, fakeUser, setFakeToken } from '../../test/authTestUtils'

vi.mock('../../api/client')

const results: ClassificationResults = {
  target_column: 'churned',
  feature_columns: ['tenure_months', 'support_tickets'],
  class_distribution: { False: 60, True: 40 },
  candidate_models: [
    { model_name: 'Logistic Regression', metrics: { roc_auc: 0.91, accuracy: 0.85 } },
    { model_name: 'Random Forest', metrics: { roc_auc: 0.88, accuracy: 0.83 } },
  ],
  selected_model: 'Logistic Regression',
  primary_metric: 'roc_auc',
  primary_metric_rationale: 'ROC-AUC handles class imbalance better than accuracy.',
  metrics: { roc_auc: 0.91, accuracy: 0.85 },
  confusion_matrix: { labels: ['False', 'True'], matrix: [[55, 5], [8, 32]] },
  feature_importance: [
    { feature: 'tenure_months', importance: 0.6, direction: 'negative' },
    { feature: 'support_tickets', importance: 0.3, direction: 'positive' },
  ],
  sample_predictions: [
    { row_index: 1, actual: 'True', predicted: 'True', probability: 0.8 },
    { row_index: 2, actual: 'False', predicted: 'True', probability: 0.6 },
  ],
  test_size: 0.25,
  random_seed: 42,
  was_sampled: false,
}

beforeEach(() => {
  setFakeToken()
  vi.mocked(apiClient.authMe).mockResolvedValue(
    fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
  )
})

describe('ClassificationResultsView', () => {
  it('highlights the selected model in the comparison table with its real metrics', async () => {
    renderWithProviders(<ClassificationResultsView runId="run-1" results={results} />)

    expect(await screen.findByText('Selected')).toBeInTheDocument()
    const selectedRow = screen.getByText('Logistic Regression').closest('tr')!
    expect(selectedRow).toHaveTextContent('0.91')
    expect(selectedRow).toHaveTextContent('0.85')
  })

  it('renders the real confusion matrix cell values', () => {
    renderWithProviders(<ClassificationResultsView runId="run-1" results={results} />)

    // 4 real counts from the matrix: 55, 5, 8, 32.
    for (const count of [55, 5, 8, 32]) {
      expect(screen.getByText(String(count))).toBeInTheDocument()
    }
  })

  it('marks a misclassified sample prediction row distinctly from a correct one', () => {
    renderWithProviders(<ClassificationResultsView runId="run-1" results={results} />)

    const correctRow = screen.getByText('1').closest('tr')!
    const wrongRow = screen.getByText('2').closest('tr')!
    expect(wrongRow.className).toContain('bg-red-50')
    expect(correctRow.className).not.toContain('bg-red-50')
  })

  it('runs a real prediction and shows the real returned summary', async () => {
    vi.mocked(apiClient.predictMlRun).mockResolvedValue({
      run_id: 'run-1',
      task_type: 'classification',
      predictions: [],
      summary: { row_count: 100, predicted_positive: 37 },
    } as never)

    renderWithProviders(<ClassificationResultsView runId="run-1" results={results} />)
    await userEvent.click(await screen.findByRole('button', { name: 'Run predictions' }))

    expect(apiClient.predictMlRun).toHaveBeenCalledWith('run-1', undefined)
    expect(await screen.findByText(/Scored 100 rows - 37 predicted positive/)).toBeInTheDocument()
  })
})
