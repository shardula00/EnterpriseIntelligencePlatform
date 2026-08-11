/** Shared helpers for tests whose components call useAuth()/usePermission(). */
import type { CurrentUser, PermissionName } from '../api/types'

const TOKEN_STORAGE_KEY = 'eip_access_token'

export const ALL_PERMISSIONS: PermissionName[] = [
  'dataset:read',
  'dataset:create',
  'dataset:delete',
  'dashboard:read',
  'dashboard:configure',
  'user:read',
  'user:create',
  'user:update',
  'user:delete',
  'audit:read',
]

export const VIEWER_PERMISSIONS: PermissionName[] = ['dataset:read', 'dashboard:read']

export function fakeUser(overrides: Partial<CurrentUser> = {}): CurrentUser {
  return {
    id: 'test-user-id',
    email: 'test-user@example.com',
    full_name: 'Test User',
    is_active: true,
    created_at: new Date().toISOString(),
    roles: ['ADMIN'],
    permissions: ALL_PERMISSIONS,
    ...overrides,
  }
}

/** AuthProvider only calls GET /auth/me at all if a token is present -
 * tests that need an authenticated user must set one before rendering. */
export function setFakeToken(): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, 'fake-test-token')
}

export function clearFakeToken(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY)
}
