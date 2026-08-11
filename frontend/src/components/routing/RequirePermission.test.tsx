import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { RequirePermission } from './RequirePermission'
import * as apiClient from '../../api/client'
import { AuthProvider } from '../../auth/AuthContext'
import { fakeUser, setFakeToken, VIEWER_PERMISSIONS } from '../../test/authTestUtils'

vi.mock('../../api/client')

function renderGated() {
  return render(
    <MemoryRouter initialEntries={['/admin/audit']}>
      <AuthProvider>
        <Routes>
          <Route
            path="/admin/audit"
            element={
              <RequirePermission permission="audit:read">
                <div>Audit log content</div>
              </RequirePermission>
            }
          />
          <Route path="/" element={<div>Datasets home</div>} />
          <Route path="/login" element={<div>Login page</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('RequirePermission', () => {
  it('redirects to /login when unauthenticated', async () => {
    renderGated()
    expect(await screen.findByText('Login page')).toBeInTheDocument()
  })

  it('redirects home when authenticated but missing the permission (Viewer)', async () => {
    setFakeToken()
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['VIEWER'], permissions: VIEWER_PERMISSIONS }),
    )

    renderGated()
    expect(await screen.findByText('Datasets home')).toBeInTheDocument()
    expect(screen.queryByText('Audit log content')).not.toBeInTheDocument()
  })

  it('renders the gated content when the user has the permission (Admin)', async () => {
    setFakeToken()
    vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser()) // full permissions, includes audit:read

    renderGated()
    expect(await screen.findByText('Audit log content')).toBeInTheDocument()
  })
})
