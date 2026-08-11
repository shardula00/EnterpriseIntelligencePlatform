import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LoginPage } from './LoginPage'
import * as apiClient from '../api/client'
import { AuthProvider } from '../auth/AuthContext'
import { fakeUser } from '../test/authTestUtils'

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client')
  return { ...actual, authLogin: vi.fn(), authMe: vi.fn() }
})

function renderLoginPage() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<div>Datasets Home</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  // No token in storage -> AuthProvider resolves to unauthenticated without
  // even calling authMe; individual tests override authLogin/authMe as needed.
  vi.mocked(apiClient.authMe).mockRejectedValue(new Error('unauthenticated'))
})

describe('LoginPage', () => {
  it('renders the sign-in form', () => {
    renderLoginPage()
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
  })

  it('logs in and navigates into the app on success', async () => {
    vi.mocked(apiClient.authLogin).mockResolvedValue({ access_token: 'tok', token_type: 'bearer' })
    vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())

    renderLoginPage()
    await userEvent.type(screen.getByLabelText('Email'), 'admin@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'Password123')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByText('Datasets Home')).toBeInTheDocument()
    expect(apiClient.authLogin).toHaveBeenCalledWith('admin@example.com', 'Password123')
  })

  it('shows the backend error message on invalid credentials, without navigating', async () => {
    vi.mocked(apiClient.authLogin).mockRejectedValue(
      new apiClient.ApiError('Incorrect email or password.', 401),
    )

    renderLoginPage()
    await userEvent.type(screen.getByLabelText('Email'), 'wrong@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'WrongPassword')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByText('Incorrect email or password.')).toBeInTheDocument()
    expect(screen.queryByText('Datasets Home')).not.toBeInTheDocument()
  })

  it('disables the submit button while the request is in flight', async () => {
    let resolveLogin!: (value: { access_token: string; token_type: string }) => void
    vi.mocked(apiClient.authLogin).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveLogin = resolve
        }),
    )

    renderLoginPage()
    await userEvent.type(screen.getByLabelText('Email'), 'admin@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'Password123')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    expect(screen.getByRole('button', { name: /signing in/i })).toBeDisabled()
    resolveLogin({ access_token: 'tok', token_type: 'bearer' })
  })
})
