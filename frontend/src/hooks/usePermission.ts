import { useAuth } from '../auth/AuthContext'
import type { PermissionName } from '../api/types'

/**
 * UX convenience only - decides what to *show*, never what to *allow*.
 * Every permission check that matters is re-enforced server-side; hiding a
 * button here just avoids showing a control the backend would reject.
 */
export function usePermission(permission: PermissionName): boolean {
  return useAuth().hasPermission(permission)
}
