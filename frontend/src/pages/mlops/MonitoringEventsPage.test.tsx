import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MonitoringEventsPage } from './MonitoringEventsPage'
import * as apiClient from '../../api/client'
import { renderWithProviders } from '../../test/renderWithProviders'
import { fakeUser, setFakeToken } from '../../test/authTestUtils'

vi.mock('../../api/client')

const baseEvent = {
  id: 'event-1',
  model_version_id: 'version-1',
  dataset_id: 'ds-2',
  event_type: 'drift' as const,
  severity: 'critical' as const,
  summary: 'Drift check: drift against \'Shifted dataset\'.',
  details: {},
  created_by: null,
  created_at: '2026-01-01T00:00:00Z',
}

beforeEach(() => {
  setFakeToken()
  vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
})

describe('MonitoringEventsPage', () => {
  it('lists real alerts with a link to the affected model version', async () => {
    vi.mocked(apiClient.listMonitoringEvents).mockResolvedValue([baseEvent])

    renderWithProviders(<MonitoringEventsPage />)

    expect(await screen.findByText(/Drift check: drift/)).toBeInTheDocument()
    // 'critical' also appears as an <option> text in the severity filter select,
    // so scope this assertion to the results table's own severity badge.
    const table = screen.getByRole('table')
    expect(within(table).getByText('critical')).toBeInTheDocument()
    const link = within(table).getByRole('link', { name: 'View version' })
    expect(link).toHaveAttribute('href', '/mlops/versions/version-1')
  })

  it('re-fetches with the selected severity filter', async () => {
    vi.mocked(apiClient.listMonitoringEvents).mockResolvedValue([baseEvent])

    renderWithProviders(<MonitoringEventsPage />)
    await screen.findByText(/Drift check: drift/)

    await userEvent.selectOptions(screen.getByLabelText('Severity'), 'warning')

    expect(apiClient.listMonitoringEvents).toHaveBeenCalledWith({ severity: 'warning' })
  })

  it('shows an empty state when there are no alerts', async () => {
    vi.mocked(apiClient.listMonitoringEvents).mockResolvedValue([])

    renderWithProviders(<MonitoringEventsPage />)

    expect(await screen.findByText('No monitoring events yet')).toBeInTheDocument()
  })

  it('shows an error message when loading fails', async () => {
    vi.mocked(apiClient.listMonitoringEvents).mockRejectedValue(new Error('alerts unavailable'))

    renderWithProviders(<MonitoringEventsPage />)

    expect(await screen.findByText(/alerts unavailable/)).toBeInTheDocument()
  })
})
