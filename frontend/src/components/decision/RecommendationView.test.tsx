import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RecommendationView } from './RecommendationView'
import type { Recommendation } from '../../api/types'
import * as apiClient from '../../api/client'
import { renderWithProviders } from '../../test/renderWithProviders'
import { ANALYST_PERMISSIONS, fakeUser, setFakeToken, VIEWER_PERMISSIONS } from '../../test/authTestUtils'

vi.mock('../../api/client')

const pendingRecommendation: Recommendation = {
  id: 'rec-1',
  dataset_id: 'ds-1',
  question: 'Forecast next quarter revenue and recommend an action if there is a risk',
  recommendation: 'Review closely before acting - a notable risk signal was detected.',
  alternatives: ['Take no action and continue monitoring.', 'Proceed with a smaller, partial action and reassess'],
  evidence: [{ agent: 'ml', tool: 'forecast', summary: 'Trained a forecast, trending down.' }],
  risks: [{ severity: 'warning', message: 'Forecast shows a declining trend.', source: 'forecast_trend' }],
  assumptions: ['No risk assessment was available for this recommendation.'],
  confidence: 'medium',
  expected_impact: null,
  status: 'pending',
  decided_by: null,
  decided_at: null,
  created_at: '2026-01-01T00:00:00Z',
}

beforeEach(() => {
  setFakeToken()
})

describe('RecommendationView', () => {
  it('renders the recommendation, alternatives, evidence, risks, and assumptions', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
    renderWithProviders(
      <RecommendationView recommendation={pendingRecommendation} onApprove={vi.fn()} onReject={vi.fn()} />,
    )

    expect(await screen.findByText(/Review closely before acting/)).toBeInTheDocument()
    expect(screen.getByText('Take no action and continue monitoring.')).toBeInTheDocument()
    expect(screen.getByText(/Trained a forecast, trending down/)).toBeInTheDocument()
    expect(screen.getByText(/Forecast shows a declining trend/)).toBeInTheDocument()
    expect(screen.getByText(/No risk assessment was available/)).toBeInTheDocument()
    expect(screen.getByText('Not quantified - no verified what-if scenario was part of this request.')).toBeInTheDocument()
  })

  it('shows Approve/Reject for a user with decision:approve and calls the right handler', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser()) // ADMIN, has decision:approve
    const onApprove = vi.fn()
    renderWithProviders(
      <RecommendationView recommendation={pendingRecommendation} onApprove={onApprove} onReject={vi.fn()} />,
    )

    await userEvent.click(await screen.findByRole('button', { name: /approve/i }))
    expect(onApprove).toHaveBeenCalled()
  })

  it('hides Approve/Reject for an Analyst (has decision:propose, not decision:approve)', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
    )
    renderWithProviders(
      <RecommendationView recommendation={pendingRecommendation} onApprove={vi.fn()} onReject={vi.fn()} />,
    )

    await screen.findByText(/Review closely before acting/)
    expect(screen.queryByRole('button', { name: /approve/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /reject/i })).not.toBeInTheDocument()
  })

  it('hides Approve/Reject for a Viewer', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['VIEWER'], permissions: VIEWER_PERMISSIONS }),
    )
    renderWithProviders(
      <RecommendationView recommendation={pendingRecommendation} onApprove={vi.fn()} onReject={vi.fn()} />,
    )

    await screen.findByText(/Review closely before acting/)
    expect(screen.queryByRole('button', { name: /approve/i })).not.toBeInTheDocument()
  })

  it('hides Approve/Reject once a recommendation is no longer pending', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
    renderWithProviders(
      <RecommendationView
        recommendation={{ ...pendingRecommendation, status: 'approved' }}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    )

    await screen.findByText(/Review closely before acting/)
    expect(screen.queryByRole('button', { name: /approve/i })).not.toBeInTheDocument()
  })

  it('renders the expected impact when present', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
    renderWithProviders(
      <RecommendationView
        recommendation={{
          ...pendingRecommendation,
          expected_impact: {
            affected_metric: 'profit',
            affected_value_change: -24000,
            relationship: 'profit = revenue - cost',
          },
        }}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    )

    expect(await screen.findByText(/profit changes by -24000/)).toBeInTheDocument()
  })
})
