/**
 * Access-token storage: localStorage (Phase 4 deliberate tradeoff).
 *
 * Why localStorage: simplest correct implementation, and this app renders
 * no user-generated HTML anywhere (no XSS sink today), so the practical
 * risk is low. The token is also short-lived (60 minutes, no refresh
 * token - see backend/app/auth/security.py), which bounds the exposure
 * window if it were ever exfiltrated.
 *
 * The real tradeoff: any script that DID get injected into this page
 * (e.g. via a future dependency with an XSS bug) could read this token
 * directly, which an httpOnly cookie would prevent. A production system
 * handling more sensitive data should use HttpOnly + Secure + SameSite
 * cookies with CSRF protection instead - deliberately not built here; see
 * frontend/README.md and ARCHITECTURE.md for the full writeup.
 */

const STORAGE_KEY = 'eip_access_token'

export function getToken(): string | null {
  return localStorage.getItem(STORAGE_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(STORAGE_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(STORAGE_KEY)
}

/** Fired whenever a request comes back 401 - AuthContext listens for this
 * to reset its state (e.g. an expired/invalidated token mid-session), so
 * ProtectedRoute redirects to /login on the next render. */
export const UNAUTHORIZED_EVENT = 'eip:unauthorized'

export function dispatchUnauthorized(): void {
  window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
}
