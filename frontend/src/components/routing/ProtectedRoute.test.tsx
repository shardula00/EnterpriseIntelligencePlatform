import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { ProtectedRoute } from './ProtectedRoute'
import * as apiClient from '../../api/client'
import { AuthProvider } from '../../auth/AuthContext'
import { fakeUser, setFakeToken } from '../../test/authTestUtils'

vi.mock('../../api/client')

function renderProtected() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <AuthProvider>
        <Routes>
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <div>Protected content</div>
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<div>Login page</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('ProtectedRoute', () => {
  it('redirects to /login when there is no token at all', async () => {
    renderProtected()
    expect(await screen.findByText('Login page')).toBeInTheDocument()
  })

  it('redirects to /login when the token is invalid/expired', async () => {
    setFakeToken()
    vi.mocked(apiClient.authMe).mockRejectedValue(new Error('expired'))

    renderProtected()
    expect(await screen.findByText('Login page')).toBeInTheDocument()
  })

  it('renders the protected content once authenticated', async () => {
    setFakeToken()
    vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())

    renderProtected()
    expect(await screen.findByText('Protected content')).toBeInTheDocument()
  })
})
