import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MlRunsHistoryPage } from './MlRunsHistoryPage'
import * as apiClient from '../../api/client'
import { renderWithProviders } from '../../test/renderWithProviders'
import { fakeUser, setFakeToken } from '../../test/authTestUtils'

vi.mock('../../api/client')

beforeEach(() => {
  setFakeToken()
  vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
})

describe('MlRunsHistoryPage', () => {
  it('lists every run with its real task label, model, and status', async () => {
    vi.mocked(apiClient.listMlRuns).mockResolvedValue([
      {
        id: 'run-1',
        dataset_id: 'ds-1',
        task_type: 'forecasting',
        model_name: 'Random Forest',
        status: 'completed',
        configuration: {},
        created_by: null,
        created_at: '2026-01-01T00:00:00Z',
        completed_at: '2026-01-01T00:00:01Z',
      },
    ] as never)

    renderWithProviders(<MlRunsHistoryPage />)

    const link = await screen.findByRole('link', { name: 'Forecasting' })
    expect(link).toHaveAttribute('href', '/ml/runs/run-1')
    expect(screen.getByText('Random Forest')).toBeInTheDocument()
    expect(screen.getByText('completed')).toBeInTheDocument()
  })

  it('shows an empty state when there are no runs', async () => {
    vi.mocked(apiClient.listMlRuns).mockResolvedValue([])

    renderWithProviders(<MlRunsHistoryPage />)

    expect(await screen.findByText('No ML runs yet')).toBeInTheDocument()
  })

  it('shows an error message when loading fails', async () => {
    vi.mocked(apiClient.listMlRuns).mockRejectedValue(new Error('server unavailable'))

    renderWithProviders(<MlRunsHistoryPage />)

    expect(await screen.findByText(/server unavailable/)).toBeInTheDocument()
  })
})
