import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MlConfigurePage } from './MlConfigurePage'
import * as apiClient from '../../api/client'
import { AuthProvider } from '../../auth/AuthContext'
import { ANALYST_PERMISSIONS, fakeUser, setFakeToken, VIEWER_PERMISSIONS } from '../../test/authTestUtils'

vi.mock('../../api/client')

const dataset = {
  id: 'ds-1',
  name: 'Churn dataset',
  original_filename: 'churn.csv',
  file_type: 'csv',
  row_count: 500,
  column_count: 4,
  quality_score: 100,
  status: 'ready',
  created_at: '2026-01-01T00:00:00Z',
}

const columns = ['tenure_months', 'monthly_charges', 'churned'].map((name, i) => ({
  position: i,
  original_name: name,
  column_name: name,
  detected_type: name === 'churned' ? 'boolean' : 'integer',
  nullable: false,
  null_count: 0,
  distinct_count: 5,
}))

function suitability(suitable: boolean) {
  return {
    dataset_id: 'ds-1',
    row_count: 500,
    tasks: [
      {
        task_type: 'classification' as const,
        suitable,
        reasons: suitable ? [] : ['No usable feature columns available.'],
        suggested_target_columns: ['churned'],
        suggested_datetime_columns: [],
        suggested_feature_columns: ['tenure_months', 'monthly_charges'],
      },
    ],
  }
}

function renderPage(taskType = 'classification') {
  return render(
    <MemoryRouter initialEntries={[`/ml/${taskType}/ds-1`]}>
      <AuthProvider>
        <Routes>
          <Route path="/ml/:taskType/:datasetId" element={<MlConfigurePage />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  setFakeToken()
})

describe('MlConfigurePage', () => {
  it('renders the classification form for a suitable dataset', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
    )
    vi.mocked(apiClient.getDataset).mockResolvedValue(dataset as never)
    vi.mocked(apiClient.getColumns).mockResolvedValue(columns as never)
    vi.mocked(apiClient.getMlSuitability).mockResolvedValue(suitability(true) as never)

    renderPage()

    expect(await screen.findByText(/Configure: Binary Classification/)).toBeInTheDocument()
    expect(screen.getByText(/Churn dataset/)).toBeInTheDocument()
    expect(screen.getByRole('combobox')).toHaveValue('churned')
  })

  it('shows the real rejection reason instead of a form for an unsuitable dataset', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
    )
    vi.mocked(apiClient.getDataset).mockResolvedValue(dataset as never)
    vi.mocked(apiClient.getColumns).mockResolvedValue(columns as never)
    vi.mocked(apiClient.getMlSuitability).mockResolvedValue(suitability(false) as never)

    renderPage()

    expect(await screen.findByText(/No usable feature columns available/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Train model' })).not.toBeInTheDocument()
  })

  it('shows an access message and never renders a training form for a Viewer (no ml:train)', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['VIEWER'], permissions: VIEWER_PERMISSIONS }),
    )
    vi.mocked(apiClient.getDataset).mockResolvedValue(dataset as never)
    vi.mocked(apiClient.getColumns).mockResolvedValue(columns as never)
    vi.mocked(apiClient.getMlSuitability).mockResolvedValue(suitability(true) as never)

    renderPage()

    expect(
      await screen.findByText(/Training a model requires Analyst or Admin access/),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Train model' })).not.toBeInTheDocument()
  })
})
