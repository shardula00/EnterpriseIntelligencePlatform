import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import type { PermissionName } from '../../api/types'
import { LoadingSpinner } from '../common/LoadingSpinner'

/**
 * Gates a whole page behind a permission (e.g. the admin Users/Audit
 * pages) - not just "logged in" (ProtectedRoute) but "logged in AND
 * allowed." This is a UX convenience: a user who reaches this page
 * without the permission is redirected home, but every API call the page
 * would make is independently rejected (403) by the backend regardless -
 * this component alone is not what makes the page secure.
 */
export function RequirePermission({
  permission,
  children,
}: {
  permission: PermissionName
  children: ReactNode
}) {
  const { status, hasPermission } = useAuth()

  if (status === 'loading') {
    return <LoadingSpinner label="Checking your session…" />
  }

  if (status === 'unauthenticated') {
    return <Navigate to="/login" replace />
  }

  if (!hasPermission(permission)) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
