import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuditLogPage } from './AuditLogPage'
import * as apiClient from '../../api/client'
import { AuthProvider } from '../../auth/AuthContext'
import { fakeUser, setFakeToken } from '../../test/authTestUtils'

vi.mock('../../api/client')

const entry = {
  id: 1,
  user_id: 'user-1',
  user_email: 'admin@example.com',
  action: 'dataset.uploaded',
  resource_type: 'dataset',
  resource_id: 'ds-1',
  event_metadata: { row_count: 20 },
  ip_address: '127.0.0.1',
  user_agent: 'test-agent',
  created_at: '2026-01-01T12:00:00Z',
}

function renderPage() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <AuditLogPage />
      </AuthProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  setFakeToken()
  vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
})

describe('AuditLogPage', () => {
  it('lists real audit events with user, action, and resource', async () => {
    vi.mocked(apiClient.listAuditLogs).mockResolvedValue({
      items: [entry],
      total: 1,
      limit: 20,
      offset: 0,
    })

    renderPage()

    expect(await screen.findByText('admin@example.com')).toBeInTheDocument()
    // "dataset.uploaded" also appears as a filter <option>, so scope to the
    // table cell's own <span>.
    expect(screen.getByText('dataset.uploaded', { selector: 'span' })).toBeInTheDocument()
    expect(screen.getByText('ds-1')).toBeInTheDocument()
    expect(screen.getByText(/"row_count": 20/)).toBeInTheDocument()
  })

  it('never renders a password or token even if present in metadata', async () => {
    vi.mocked(apiClient.listAuditLogs).mockResolvedValue({
      items: [{ ...entry, event_metadata: { attempted_email: 'x@example.com' } }],
      total: 1,
      limit: 20,
      offset: 0,
    })

    renderPage()

    await screen.findByText('admin@example.com')
    expect(screen.queryByText(/password/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Bearer /)).not.toBeInTheDocument()
  })

  it('shows an empty state when there are no matching events', async () => {
    vi.mocked(apiClient.listAuditLogs).mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 })

    renderPage()

    expect(await screen.findByText('No audit events')).toBeInTheDocument()
  })

  it('re-fetches with the selected action filter', async () => {
    vi.mocked(apiClient.listAuditLogs).mockResolvedValue({
      items: [entry],
      total: 1,
      limit: 20,
      offset: 0,
    })

    renderPage()
    await screen.findByText('admin@example.com')

    await userEvent.selectOptions(screen.getByLabelText('Action'), 'dataset.uploaded')

    await waitFor(() =>
      expect(apiClient.listAuditLogs).toHaveBeenCalledWith({
        limit: 20,
        offset: 0,
        action: 'dataset.uploaded',
      }),
    )
  })

  it('paginates using Previous/Next', async () => {
    vi.mocked(apiClient.listAuditLogs).mockResolvedValue({
      items: [entry],
      total: 50,
      limit: 20,
      offset: 0,
    })

    renderPage()
    await screen.findByText('admin@example.com')

    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() =>
      expect(apiClient.listAuditLogs).toHaveBeenCalledWith({
        limit: 20,
        offset: 20,
        action: undefined,
      }),
    )
  })
})
