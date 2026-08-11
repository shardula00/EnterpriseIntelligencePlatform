import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MlDatasetSelectionPage } from './MlDatasetSelectionPage'
import * as apiClient from '../../api/client'
import { AuthProvider } from '../../auth/AuthContext'
import { fakeUser, setFakeToken } from '../../test/authTestUtils'

vi.mock('../../api/client')

const suitableDataset = {
  id: 'ds-suitable',
  name: 'Churn dataset',
  original_filename: 'churn.csv',
  file_type: 'csv',
  row_count: 500,
  column_count: 7,
  quality_score: 100,
  status: 'ready',
  created_at: '2026-01-01T00:00:00Z',
}

const unsuitableDataset = {
  ...suitableDataset,
  id: 'ds-unsuitable',
  name: 'Sales time series',
}

function suitabilityFor(datasetId: string, suitable: boolean) {
  return {
    dataset_id: datasetId,
    row_count: 500,
    tasks: [
      {
        task_type: 'classification' as const,
        suitable,
        reasons: suitable ? [] : ['No binary target column was found.'],
        suggested_target_columns: [],
        suggested_datetime_columns: [],
        suggested_feature_columns: [],
      },
      { task_type: 'forecasting' as const, suitable: false, reasons: [] },
      { task_type: 'segmentation' as const, suitable: false, reasons: [] },
      { task_type: 'anomaly_detection' as const, suitable: false, reasons: [] },
    ],
  }
}

function renderPage(taskType = 'classification') {
  return render(
    <MemoryRouter initialEntries={[`/ml/${taskType}`]}>
      <AuthProvider>
        <Routes>
          <Route path="/ml/:taskType" element={<MlDatasetSelectionPage />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  setFakeToken()
  vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
})

describe('MlDatasetSelectionPage', () => {
  it('links a suitable dataset to its configure page', async () => {
    vi.mocked(apiClient.listDatasets).mockResolvedValue([suitableDataset] as never)
    vi.mocked(apiClient.getMlSuitability).mockResolvedValue(suitabilityFor('ds-suitable', true) as never)

    renderPage()

    const link = await screen.findByRole('link', { name: /Churn dataset/ })
    expect(link).toHaveAttribute('href', '/ml/classification/ds-suitable')
    expect(screen.getByText('Suitable')).toBeInTheDocument()
  })

  it('shows an unsuitable dataset as non-clickable with its real rejection reason', async () => {
    vi.mocked(apiClient.listDatasets).mockResolvedValue([unsuitableDataset] as never)
    vi.mocked(apiClient.getMlSuitability).mockResolvedValue(
      suitabilityFor('ds-unsuitable', false) as never,
    )

    renderPage()

    expect(await screen.findByText('Not suitable')).toBeInTheDocument()
    expect(screen.getByText('No binary target column was found.')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Sales time series/ })).not.toBeInTheDocument()
  })

  it('checks suitability for every dataset independently', async () => {
    vi.mocked(apiClient.listDatasets).mockResolvedValue([
      suitableDataset,
      unsuitableDataset,
    ] as never)
    vi.mocked(apiClient.getMlSuitability).mockImplementation((id: string) =>
      Promise.resolve(suitabilityFor(id, id === 'ds-suitable') as never),
    )

    renderPage()

    expect(await screen.findByText('Suitable')).toBeInTheDocument()
    expect(screen.getByText('Not suitable')).toBeInTheDocument()
    expect(apiClient.getMlSuitability).toHaveBeenCalledWith('ds-suitable')
    expect(apiClient.getMlSuitability).toHaveBeenCalledWith('ds-unsuitable')
  })

  it('redirects to /ml for an unknown task type', async () => {
    render(
      <MemoryRouter initialEntries={['/ml/not-a-real-task']}>
        <AuthProvider>
          <Routes>
            <Route path="/ml/:taskType" element={<MlDatasetSelectionPage />} />
            <Route path="/ml" element={<div>Task selection page</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    )

    expect(await screen.findByText('Task selection page')).toBeInTheDocument()
  })

  it('shows an empty state when there are no datasets at all', async () => {
    vi.mocked(apiClient.listDatasets).mockResolvedValue([])

    renderPage()

    expect(await screen.findByText('No datasets yet')).toBeInTheDocument()
  })
})
