import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AnomalyResultsView } from './AnomalyResultsView'
import type { AnomalyResults } from '../../api/types'
import * as apiClient from '../../api/client'
import { renderWithProviders } from '../../test/renderWithProviders'
import { ANALYST_PERMISSIONS, fakeUser, setFakeToken } from '../../test/authTestUtils'

vi.mock('../../api/client')

const results: AnomalyResults = {
  feature_columns: ['amount', 'distance_from_home_km'],
  contamination: 0.05,
  anomaly_count: 25,
  anomaly_percentage: 5.0,
  anomalous_records: [
    {
      row_index: 412,
      anomaly_score: 0.91,
      is_anomaly: true,
      values: { amount: 980.5, distance_from_home_km: 210 },
    },
    {
      row_index: 88,
      anomaly_score: 0.77,
      is_anomaly: true,
      values: { amount: 850, distance_from_home_km: 180 },
    },
  ],
  score_summary: { min: -0.2, max: 0.91, mean: 0.05 },
  random_seed: 42,
  was_sampled: false,
}

beforeEach(() => {
  setFakeToken()
  vi.mocked(apiClient.authMe).mockResolvedValue(
    fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
  )
})

describe('AnomalyResultsView', () => {
  it('shows the real contamination rate and flagged count/percentage', () => {
    renderWithProviders(<AnomalyResultsView runId="run-1" results={results} />)

    expect(screen.getByText('5%')).toBeInTheDocument()
    expect(screen.getByText(/25 \(5%\)/)).toBeInTheDocument()
  })

  it('lists flagged records sorted with their real row index, score, and feature values', () => {
    renderWithProviders(<AnomalyResultsView runId="run-1" results={results} />)

    const topRow = screen.getByText('412').closest('tr')!
    expect(topRow).toHaveTextContent('0.91')
    expect(topRow).toHaveTextContent('980.5')
    expect(topRow).toHaveTextContent('210')
  })

  it('scores all rows via the real predict action and shows the real returned summary', async () => {
    vi.mocked(apiClient.predictMlRun).mockResolvedValue({
      run_id: 'run-1',
      task_type: 'anomaly_detection',
      predictions: [],
      summary: { row_count: 500, anomaly_count: 25 },
    } as never)

    renderWithProviders(<AnomalyResultsView runId="run-1" results={results} />)
    await userEvent.click(await screen.findByRole('button', { name: 'Run predictions' }))

    expect(apiClient.predictMlRun).toHaveBeenCalledWith('run-1', undefined)
    expect(await screen.findByText(/Scored 500 rows - 25 flagged as anomalous/)).toBeInTheDocument()
  })
})
