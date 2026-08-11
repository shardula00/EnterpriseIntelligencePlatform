import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MlTaskSelectionPage } from './MlTaskSelectionPage'
import * as apiClient from '../../api/client'
import { renderWithProviders } from '../../test/renderWithProviders'
import { ANALYST_PERMISSIONS, fakeUser, setFakeToken, VIEWER_PERMISSIONS } from '../../test/authTestUtils'

vi.mock('../../api/client')

beforeEach(() => {
  setFakeToken()
})

describe('MlTaskSelectionPage', () => {
  it('renders all 4 task cards as enabled links for an Analyst', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
    )
    vi.mocked(apiClient.listMlRuns).mockResolvedValue([])

    renderWithProviders(<MlTaskSelectionPage />)

    const classificationLink = await screen.findByRole('link', { name: /Binary Classification/ })
    expect(classificationLink).toHaveAttribute('href', '/ml/classification')
    expect(screen.getByRole('link', { name: /Time-Series Forecasting/ })).toHaveAttribute(
      'href',
      '/ml/forecasting',
    )
    expect(screen.getByRole('link', { name: /Customer Segmentation/ })).toHaveAttribute(
      'href',
      '/ml/segmentation',
    )
    expect(screen.getByRole('link', { name: /Anomaly Detection/ })).toHaveAttribute(
      'href',
      '/ml/anomaly_detection',
    )
  })

  it('disables task cards and shows an upgrade message for a Viewer (no ml:train)', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['VIEWER'], permissions: VIEWER_PERMISSIONS }),
    )
    vi.mocked(apiClient.listMlRuns).mockResolvedValue([])

    renderWithProviders(<MlTaskSelectionPage />)

    const classificationLink = await screen.findByRole('link', { name: /Binary Classification/ })
    expect(classificationLink).toHaveAttribute('aria-disabled', 'true')
    expect(await screen.findByText(/Training requires Analyst or Admin access/)).toBeInTheDocument()
  })

  it('shows real recent runs, linking each to its own run page', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
    )
    vi.mocked(apiClient.listMlRuns).mockResolvedValue([
      {
        id: 'run-1',
        dataset_id: 'ds-1',
        task_type: 'classification',
        model_name: 'Logistic Regression',
        status: 'completed',
        configuration: {},
        created_by: null,
        created_at: '2026-01-01T00:00:00Z',
        completed_at: '2026-01-01T00:00:01Z',
      },
    ])

    renderWithProviders(<MlTaskSelectionPage />)

    const runLink = await screen.findByRole('link', { name: 'Classification' })
    expect(runLink).toHaveAttribute('href', '/ml/runs/run-1')
    expect(screen.getByText('Logistic Regression')).toBeInTheDocument()
  })

  it('shows an empty state when there are no runs yet', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
    )
    vi.mocked(apiClient.listMlRuns).mockResolvedValue([])

    renderWithProviders(<MlTaskSelectionPage />)

    expect(await screen.findByText('No ML runs yet')).toBeInTheDocument()
  })

  it('shows an error message when loading runs fails', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
    vi.mocked(apiClient.listMlRuns).mockRejectedValue(new Error('runs unavailable'))

    renderWithProviders(<MlTaskSelectionPage />)

    expect(await screen.findByText(/runs unavailable/)).toBeInTheDocument()
  })
})
