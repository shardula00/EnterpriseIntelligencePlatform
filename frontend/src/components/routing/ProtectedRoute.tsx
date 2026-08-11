import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { LoadingSpinner } from '../common/LoadingSpinner'

/** Requires only that the user is authenticated - used for the main app
 * routes (dataset list/detail). Permission-specific gating is
 * RequirePermission, below. */
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') {
    return <LoadingSpinner label="Checking your session…" />
  }

  if (status === 'unauthenticated') {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }

  return <>{children}</>
}
