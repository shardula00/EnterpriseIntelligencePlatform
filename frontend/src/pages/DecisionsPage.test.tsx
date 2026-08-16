import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DecisionsPage } from './DecisionsPage'
import * as apiClient from '../api/client'
import { renderWithProviders } from '../test/renderWithProviders'
import { ANALYST_PERMISSIONS, fakeUser, setFakeToken } from '../test/authTestUtils'
import type { DatasetSummary, Recommendation, ScenarioResult } from '../api/types'

// A partial mock (keeping the real ApiError class via importActual) - see
// AnalyticsPage.test.tsx/DocumentUploadForm.test.tsx for why a full
// vi.mock('../api/client') automock would break `err instanceof ApiError`.
vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client')
  return {
    ...actual,
    authMe: vi.fn(),
    listDatasets: vi.fn(),
    runScenario: vi.fn(),
    proposeRecommendation: vi.fn(),
    approveRecommendation: vi.fn(),
    rejectRecommendation: vi.fn(),
  }
})

const dataset: DatasetSummary = {
  id: 'ds-1',
  name: 'decision_finance_sample',
  original_filename: 'decision_finance_sample.csv',
  file_type: 'csv',
  storage_schema: 'ingested',
  storage_table_name: 'ds_1',
  row_count: 15,
  column_count: 6,
  quality_score: 100,
  status: 'ready',
  created_at: '2026-01-01T00:00:00Z',
}

const scenarioResult: ScenarioResult = {
  computed: true,
  question: 'What happens to profit if revenue decreases by 10%?',
  affected_metric: 'profit',
  perturbed_metric: 'revenue',
  delta_percent: -10,
  baseline_perturbed_value: 240000,
  baseline_affected_value: 76000,
  new_perturbed_value: 216000,
  new_affected_value: 52000,
  affected_value_change: -24000,
  relationship: 'profit = revenue - cost',
  note: "This is a linear extrapolation using the verified relationship 'profit = revenue - cost'.",
  reason: null,
}

const pendingRecommendation: Recommendation = {
  id: 'rec-1',
  dataset_id: 'ds-1',
  question: 'recommend an action',
  recommendation: 'No significant risk signals were detected; continuing the current approach appears reasonable.',
  alternatives: ['Take no action and continue monitoring.'],
  evidence: [],
  risks: [],
  assumptions: ['No forecast was available - this recommendation is based on risk/monitoring signals only.'],
  confidence: 'medium',
  expected_impact: null,
  status: 'pending',
  decided_by: null,
  decided_at: null,
  created_at: '2026-01-01T00:00:00Z',
}

beforeEach(() => {
  setFakeToken()
  vi.mocked(apiClient.authMe).mockResolvedValue(
    fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
  )
})

describe('DecisionsPage', () => {
  it('shows an empty state when there are no datasets to select', async () => {
    vi.mocked(apiClient.listDatasets).mockResolvedValue([])
    renderWithProviders(<DecisionsPage />)
    expect(await screen.findByText('No datasets yet')).toBeInTheDocument()
  })

  it('runs a what-if scenario and shows the verified result', async () => {
    vi.mocked(apiClient.listDatasets).mockResolvedValue([dataset])
    vi.mocked(apiClient.runScenario).mockResolvedValue(scenarioResult)

    renderWithProviders(<DecisionsPage />)

    await userEvent.selectOptions(await screen.findByLabelText(/dataset/i), 'ds-1')
    await userEvent.type(
      screen.getByLabelText(/question/i),
      'What happens to profit if revenue decreases by 10%?',
    )
    await userEvent.click(screen.getByRole('button', { name: /run what-if scenario/i }))

    expect(await screen.findByText('Computed')).toBeInTheDocument()
    expect(screen.getByText('-24,000')).toBeInTheDocument()
    expect(apiClient.runScenario).toHaveBeenCalledWith(
      'ds-1',
      'What happens to profit if revenue decreases by 10%?',
    )
  })

  it('proposes a recommendation and shows it as pending', async () => {
    vi.mocked(apiClient.listDatasets).mockResolvedValue([dataset])
    vi.mocked(apiClient.proposeRecommendation).mockResolvedValue(pendingRecommendation)

    renderWithProviders(<DecisionsPage />)

    await userEvent.selectOptions(await screen.findByLabelText(/dataset/i), 'ds-1')
    await userEvent.type(screen.getByLabelText(/question/i), 'recommend an action')
    await userEvent.click(screen.getByRole('button', { name: /propose recommendation/i }))

    expect(await screen.findByText(/No significant risk signals were detected/)).toBeInTheDocument()
    expect(screen.getByText('pending')).toBeInTheDocument()
    expect(apiClient.proposeRecommendation).toHaveBeenCalledWith('ds-1', 'recommend an action')
  })

  it('approves a pending recommendation and reflects the new status', async () => {
    // Approve/Reject only render for a user with decision:approve, which is
    // ADMIN-only - override the ANALYST default from beforeEach.
    vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
    vi.mocked(apiClient.listDatasets).mockResolvedValue([dataset])
    vi.mocked(apiClient.proposeRecommendation).mockResolvedValue(pendingRecommendation)
    vi.mocked(apiClient.approveRecommendation).mockResolvedValue({
      ...pendingRecommendation,
      status: 'approved',
      decided_by: 'admin-id',
      decided_at: '2026-01-02T00:00:00Z',
    })

    renderWithProviders(<DecisionsPage />)

    await userEvent.selectOptions(await screen.findByLabelText(/dataset/i), 'ds-1')
    await userEvent.type(screen.getByLabelText(/question/i), 'recommend an action')
    await userEvent.click(screen.getByRole('button', { name: /propose recommendation/i }))
    await screen.findByText('pending')

    await userEvent.click(screen.getByRole('button', { name: /approve/i }))

    expect(await screen.findByText('approved')).toBeInTheDocument()
    expect(apiClient.approveRecommendation).toHaveBeenCalledWith('rec-1')
  })

  it('shows an error message when the scenario request fails', async () => {
    vi.mocked(apiClient.listDatasets).mockResolvedValue([dataset])
    vi.mocked(apiClient.runScenario).mockRejectedValue(new apiClient.ApiError('Dataset not found.', 404))

    renderWithProviders(<DecisionsPage />)

    await userEvent.selectOptions(await screen.findByLabelText(/dataset/i), 'ds-1')
    await userEvent.type(screen.getByLabelText(/question/i), 'what happens if revenue drops 10%?')
    await userEvent.click(screen.getByRole('button', { name: /run what-if scenario/i }))

    expect(await screen.findByText(/Dataset not found\./)).toBeInTheDocument()
  })

  it('shows an error message when loading datasets fails', async () => {
    vi.mocked(apiClient.listDatasets).mockRejectedValue(new Error('datasets unavailable'))
    renderWithProviders(<DecisionsPage />)
    expect(await screen.findByText(/datasets unavailable/)).toBeInTheDocument()
  })
})
