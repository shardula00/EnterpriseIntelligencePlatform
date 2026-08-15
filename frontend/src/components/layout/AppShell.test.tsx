import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { AppShell } from './AppShell'
import * as apiClient from '../../api/client'
import { AuthProvider } from '../../auth/AuthContext'
import { fakeUser, setFakeToken, VIEWER_PERMISSIONS } from '../../test/authTestUtils'

vi.mock('../../api/client')

function renderShell() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<AppShell>content</AppShell>} />
          <Route path="/login" element={<div>Login page</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('AppShell', () => {
  it('shows Sign in / Register links, not the user menu, when unauthenticated', async () => {
    renderShell()
    expect(await screen.findByRole('link', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Register' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /log out/i })).not.toBeInTheDocument()
  })

  it('shows Users and Audit Log links for an Admin', async () => {
    setFakeToken()
    vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())

    renderShell()
    expect(await screen.findByRole('button', { name: /log out/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Users' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Audit Log' })).toBeInTheDocument()
  })

  it('hides Users and Audit Log links for a Viewer', async () => {
    setFakeToken()
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['VIEWER'], permissions: VIEWER_PERMISSIONS }),
    )

    renderShell()
    await screen.findByRole('button', { name: /log out/i })
    expect(screen.queryByRole('link', { name: 'Users' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Audit Log' })).not.toBeInTheDocument()
  })

  it('shows the ML link for any authenticated user with ml:read, including a Viewer', async () => {
    setFakeToken()
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['VIEWER'], permissions: VIEWER_PERMISSIONS }),
    )

    renderShell()
    expect(await screen.findByRole('link', { name: 'ML' })).toHaveAttribute('href', '/ml')
  })

  it('hides the ML link when the user has no ml:read permission', async () => {
    setFakeToken()
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['VIEWER'], permissions: ['dataset:read'] }),
    )

    renderShell()
    await screen.findByRole('button', { name: /log out/i })
    expect(screen.queryByRole('link', { name: 'ML' })).not.toBeInTheDocument()
  })

  it('shows the MLOps link for any authenticated user with mlops:read, including a Viewer', async () => {
    setFakeToken()
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['VIEWER'], permissions: VIEWER_PERMISSIONS }),
    )

    renderShell()
    expect(await screen.findByRole('link', { name: 'MLOps' })).toHaveAttribute('href', '/mlops')
  })

  it('hides the MLOps link when the user has no mlops:read permission', async () => {
    setFakeToken()
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['VIEWER'], permissions: ['dataset:read'] }),
    )

    renderShell()
    await screen.findByRole('button', { name: /log out/i })
    expect(screen.queryByRole('link', { name: 'MLOps' })).not.toBeInTheDocument()
  })

  it('shows the RAG link for any authenticated user with rag:read, including a Viewer', async () => {
    setFakeToken()
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['VIEWER'], permissions: VIEWER_PERMISSIONS }),
    )

    renderShell()
    expect(await screen.findByRole('link', { name: 'RAG' })).toHaveAttribute('href', '/rag')
  })

  it('hides the RAG link when the user has no rag:read permission', async () => {
    setFakeToken()
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['VIEWER'], permissions: ['dataset:read'] }),
    )

    renderShell()
    await screen.findByRole('button', { name: /log out/i })
    expect(screen.queryByRole('link', { name: 'RAG' })).not.toBeInTheDocument()
  })

  it('shows the Analytics link for any authenticated user with analytics:read, including a Viewer', async () => {
    setFakeToken()
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['VIEWER'], permissions: VIEWER_PERMISSIONS }),
    )

    renderShell()
    expect(await screen.findByRole('link', { name: 'Analytics' })).toHaveAttribute(
      'href',
      '/analytics',
    )
  })

  it('hides the Analytics link when the user has no analytics:read permission', async () => {
    setFakeToken()
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['VIEWER'], permissions: ['dataset:read'] }),
    )

    renderShell()
    await screen.findByRole('button', { name: /log out/i })
    expect(screen.queryByRole('link', { name: 'Analytics' })).not.toBeInTheDocument()
  })

  it('logs out and returns to the login page when Log out is clicked', async () => {
    setFakeToken()
    vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
    vi.mocked(apiClient.authLogout).mockResolvedValue(undefined)

    renderShell()
    await userEvent.click(await screen.findByRole('button', { name: /log out/i }))

    expect(await screen.findByText('Login page')).toBeInTheDocument()
    expect(apiClient.authLogout).toHaveBeenCalled()
  })
})
