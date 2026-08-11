import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RegisterPage } from './RegisterPage'
import * as apiClient from '../api/client'
import { AuthProvider } from '../auth/AuthContext'

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client')
  return { ...actual, authRegister: vi.fn(), authMe: vi.fn() }
})

function renderRegisterPage() {
  return render(
    <MemoryRouter initialEntries={['/register']}>
      <AuthProvider>
        <Routes>
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/login" element={<div>Sign-in page</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.mocked(apiClient.authMe).mockRejectedValue(new Error('unauthenticated'))
})

async function fillForm(name: string, email: string, password: string) {
  await userEvent.type(screen.getByLabelText('Full name'), name)
  await userEvent.type(screen.getByLabelText('Email'), email)
  await userEvent.type(screen.getByLabelText(/^Password/), password)
}

describe('RegisterPage', () => {
  it('renders the registration form and explains the default role', () => {
    renderRegisterPage()
    expect(screen.getByRole('heading', { name: 'Create an account' })).toBeInTheDocument()
    expect(screen.getByText(/start with read-only \(Viewer\) access/)).toBeInTheDocument()
  })

  it('registers successfully and redirects to the sign-in page', async () => {
    vi.mocked(apiClient.authRegister).mockResolvedValue({
      id: 'new-user',
      email: 'new@example.com',
      full_name: 'New User',
      is_active: true,
      created_at: new Date().toISOString(),
      roles: ['VIEWER'],
      permissions: ['dataset:read', 'dashboard:read'],
    })

    renderRegisterPage()
    await fillForm('New User', 'new@example.com', 'Password123')
    await userEvent.click(screen.getByRole('button', { name: /create account/i }))

    expect(await screen.findByText('Sign-in page')).toBeInTheDocument()
    expect(apiClient.authRegister).toHaveBeenCalledWith('new@example.com', 'Password123', 'New User')
  })

  it('rejects a too-short password client-side without calling the API', async () => {
    renderRegisterPage()
    await fillForm('New User', 'new@example.com', 'short')
    await userEvent.click(screen.getByRole('button', { name: /create account/i }))

    expect(await screen.findByText(/at least 8 characters/)).toBeInTheDocument()
    expect(apiClient.authRegister).not.toHaveBeenCalled()
  })

  it('shows the backend error message on a duplicate-email response', async () => {
    vi.mocked(apiClient.authRegister).mockRejectedValue(
      new apiClient.ApiError("An account with email 'new@example.com' already exists.", 409),
    )

    renderRegisterPage()
    await fillForm('New User', 'new@example.com', 'Password123')
    await userEvent.click(screen.getByRole('button', { name: /create account/i }))

    expect(await screen.findByText(/already exists/)).toBeInTheDocument()
  })
})
