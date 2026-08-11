import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { authLogin, authLogout, authMe, authRegister } from '../api/client'
import type { CurrentUser } from '../api/types'
import { getToken, UNAUTHORIZED_EVENT } from './tokenStorage'

type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated'

interface AuthContextValue {
  status: AuthStatus
  user: CurrentUser | null
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, fullName: string) => Promise<void>
  logout: () => Promise<void>
  /** UX only - the backend is always the authority. See usePermission.ts. */
  hasPermission: (permission: string) => boolean
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading')
  const [user, setUser] = useState<CurrentUser | null>(null)

  const loadCurrentUser = useCallback(async () => {
    if (!getToken()) {
      setUser(null)
      setStatus('unauthenticated')
      return
    }
    try {
      const me = await authMe()
      setUser(me)
      setStatus('authenticated')
    } catch {
      // Token missing/expired/invalidated - authMe's 401 already cleared
      // it via the client.ts middleware.
      setUser(null)
      setStatus('unauthenticated')
    }
  }, [])

  // Load on mount (e.g. a page refresh with a token already in localStorage).
  useEffect(() => {
    void loadCurrentUser()
  }, [loadCurrentUser])

  // React to a 401 that happens mid-session on some *other* request (e.g.
  // the token expired, or an admin deactivated this user) - see
  // client.ts's response middleware, which fires this event.
  useEffect(() => {
    function handleUnauthorized() {
      setUser(null)
      setStatus('unauthenticated')
    }
    window.addEventListener(UNAUTHORIZED_EVENT, handleUnauthorized)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, handleUnauthorized)
  }, [])

  const login = useCallback(
    async (email: string, password: string) => {
      await authLogin(email, password)
      await loadCurrentUser()
    },
    [loadCurrentUser],
  )

  const register = useCallback(async (email: string, password: string, fullName: string) => {
    await authRegister(email, password, fullName)
    // Deliberately does not log the new user in - registration and login
    // are separate steps (a new account is VIEWER by default; requiring an
    // explicit login keeps that boundary clear rather than silently
    // starting an authenticated session from the registration form).
  }, [])

  const logout = useCallback(async () => {
    await authLogout()
    setUser(null)
    setStatus('unauthenticated')
  }, [])

  const hasPermission = useCallback(
    (permission: string) => user?.permissions.includes(permission) ?? false,
    [user],
  )

  return (
    <AuthContext.Provider value={{ status, user, login, register, logout, hasPermission }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return ctx
}
