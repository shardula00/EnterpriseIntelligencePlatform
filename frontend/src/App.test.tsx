import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import * as apiClient from './api/client'
import { renderWithProviders } from './test/renderWithProviders'
import { fakeUser, setFakeToken, VIEWER_PERMISSIONS } from './test/authTestUtils'

// Phase 12: App.tsx (the route table itself) had zero test coverage -
// every individual page has its own dedicated test, but nothing proved the
// routes actually wire ProtectedRoute/RequirePermission to the right page.
// A smoke test per route class (public, authenticated-only, permission-
// gated - both allowed and denied) catches a route-table typo without
// duplicating each page's own detailed test suite.
vi.mock('./api/client', async () => {
  const actual = await vi.importActual<typeof import('./api/client')>('./api/client')
  return { ...actual, authMe: vi.fn(), listDatasets: vi.fn() }
})

beforeEach(() => {
  vi.mocked(apiClient.listDatasets).mockResolvedValue([])
})

describe('App routing', () => {
  it('redirects an unauthenticated visitor at "/" to the login page', async () => {
    renderWithProviders(<App />, { route: '/' })
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('renders the Datasets page at "/" for an authenticated user', async () => {
    setFakeToken()
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['VIEWER'], permissions: VIEWER_PERMISSIONS }),
    )
    renderWithProviders(<App />, { route: '/' })
    expect(await screen.findByRole('heading', { name: 'Datasets' })).toBeInTheDocument()
  })

  it('redirects home instead of rendering an admin-only route the user lacks permission for', async () => {
    setFakeToken()
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['VIEWER'], permissions: VIEWER_PERMISSIONS }),
    )
    renderWithProviders(<App />, { route: '/admin/users' })
    expect(await screen.findByRole('heading', { name: 'Datasets' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /users/i })).not.toBeInTheDocument()
  })

  it('renders a permission-gated route for a user who has that permission', async () => {
    setFakeToken()
    vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser()) // ADMIN: every permission
    renderWithProviders(<App />, { route: '/decisions' })
    expect(await screen.findByRole('heading', { name: 'Decision Intelligence' })).toBeInTheDocument()
  })
})
