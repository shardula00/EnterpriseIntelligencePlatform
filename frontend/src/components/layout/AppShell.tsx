import type { ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { usePermission } from '../../hooks/usePermission'

export function AppShell({ children }: { children: ReactNode }) {
  const { status, user, logout } = useAuth()
  const canManageUsers = usePermission('user:read')
  const canViewAudit = usePermission('audit:read')
  const canViewMl = usePermission('ml:read')
  const canViewMlOps = usePermission('mlops:read')
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link to="/" className="flex items-baseline gap-2">
            <span className="text-lg font-semibold text-slate-900">Enterprise Intelligence</span>
            <span className="text-xs font-medium text-slate-400">Platform</span>
          </Link>
          <nav className="flex items-center gap-5 text-sm text-slate-500">
            {status === 'authenticated' ? (
              <>
                <Link to="/" className="hover:text-accent-600">
                  Datasets
                </Link>
                {canViewMl && (
                  <Link to="/ml" className="hover:text-accent-600">
                    ML
                  </Link>
                )}
                {canViewMlOps && (
                  <Link to="/mlops" className="hover:text-accent-600">
                    MLOps
                  </Link>
                )}
                {canManageUsers && (
                  <Link to="/admin/users" className="hover:text-accent-600">
                    Users
                  </Link>
                )}
                {canViewAudit && (
                  <Link to="/admin/audit" className="hover:text-accent-600">
                    Audit Log
                  </Link>
                )}
                <span className="hidden text-xs text-slate-400 sm:inline">
                  {user?.full_name} · {user?.roles.join(', ')}
                </span>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100"
                >
                  Log out
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className="hover:text-accent-600">
                  Sign in
                </Link>
                <Link to="/register" className="hover:text-accent-600">
                  Register
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
    </div>
  )
}
