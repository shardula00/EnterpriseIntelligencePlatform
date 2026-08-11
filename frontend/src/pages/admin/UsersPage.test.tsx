import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { UsersPage } from './UsersPage'
import * as apiClient from '../../api/client'
import { AuthProvider } from '../../auth/AuthContext'
import { fakeUser, setFakeToken } from '../../test/authTestUtils'

vi.mock('../../api/client')

const currentAdmin = fakeUser({ id: 'admin-1', email: 'admin@example.com' })

const otherUser = {
  id: 'user-2',
  email: 'viewer@example.com',
  full_name: 'Viewer Person',
  is_active: true,
  roles: ['VIEWER'],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const roles = [
  { id: 1, name: 'ADMIN', description: null },
  { id: 2, name: 'ANALYST', description: null },
  { id: 3, name: 'VIEWER', description: null },
]

function renderPage() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <UsersPage />
      </AuthProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  setFakeToken()
  vi.mocked(apiClient.authMe).mockResolvedValue(currentAdmin)
  vi.mocked(apiClient.listRoles).mockResolvedValue(roles)
})

describe('UsersPage', () => {
  it('lists real users from the API', async () => {
    vi.mocked(apiClient.listUsers).mockResolvedValue([otherUser as never])

    renderPage()

    expect(await screen.findByText('Viewer Person')).toBeInTheDocument()
    expect(screen.getByText('viewer@example.com')).toBeInTheDocument()
  })

  it('shows an empty state when there are no users', async () => {
    vi.mocked(apiClient.listUsers).mockResolvedValue([])

    renderPage()

    expect(await screen.findByText('No users yet')).toBeInTheDocument()
  })

  it('creates a user via the form', async () => {
    vi.mocked(apiClient.listUsers).mockResolvedValue([])
    vi.mocked(apiClient.createUser).mockResolvedValue({ ...otherUser, id: 'user-3' } as never)

    renderPage()
    await screen.findByText('No users yet')

    await userEvent.type(screen.getByLabelText('Full name'), 'New Person')
    await userEvent.type(screen.getByLabelText('Email'), 'newperson@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'Password123')
    await userEvent.click(screen.getByRole('button', { name: /^create$/i }))

    await waitFor(() =>
      expect(apiClient.createUser).toHaveBeenCalledWith(
        'newperson@example.com',
        'Password123',
        'New Person',
      ),
    )
  })

  it('deactivates a user via the row action', async () => {
    vi.mocked(apiClient.listUsers).mockResolvedValue([otherUser as never])
    vi.mocked(apiClient.updateUser).mockResolvedValue({ ...otherUser, is_active: false } as never)

    renderPage()
    await screen.findByText('Viewer Person')

    await userEvent.click(screen.getByRole('button', { name: /deactivate/i }))

    expect(apiClient.updateUser).toHaveBeenCalledWith('user-2', { isActive: false })
  })

  it('disables self-modification controls on the current admin row', async () => {
    vi.mocked(apiClient.listUsers).mockResolvedValue([currentAdmin as never])

    renderPage()
    await screen.findByText(/\(you\)/)

    expect(screen.getByRole('button', { name: /deactivate/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /delete/i })).toBeDisabled()
    for (const checkbox of screen.getAllByRole('checkbox')) {
      expect(checkbox).toBeDisabled()
    }
  })

  it('assigns a new role via the checkboxes', async () => {
    vi.mocked(apiClient.listUsers).mockResolvedValue([otherUser as never])
    vi.mocked(apiClient.assignRoles).mockResolvedValue({ ...otherUser, roles: ['VIEWER', 'ANALYST'] } as never)

    renderPage()
    await screen.findByText('Viewer Person')

    await userEvent.click(screen.getByRole('checkbox', { name: 'ANALYST' }))
    await userEvent.click(screen.getByRole('button', { name: /save roles/i }))

    await waitFor(() =>
      expect(apiClient.assignRoles).toHaveBeenCalledWith('user-2', ['VIEWER', 'ANALYST']),
    )
  })
})
