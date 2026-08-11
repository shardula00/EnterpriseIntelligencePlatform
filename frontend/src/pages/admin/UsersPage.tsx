import { useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { ApiError, assignRoles, createUser, deleteUser, listRoles, listUsers, updateUser } from '../../api/client'
import type { RoleInfo, UserAdmin } from '../../api/types'
import { useAsync } from '../../hooks/useAsync'
import { LoadingSpinner } from '../../components/common/LoadingSpinner'
import { ErrorMessage } from '../../components/common/ErrorMessage'
import { EmptyState } from '../../components/common/EmptyState'

const inputClass =
  'block w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-accent-500 focus:outline-none'

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="text-xs text-slate-500">
      <span className="mb-1 block font-medium">{label}</span>
      {children}
    </label>
  )
}

export function UsersPage() {
  const { user: currentUser } = useAuth()
  const [refreshKey, setRefreshKey] = useState(0)
  const usersResult = useAsync(() => listUsers(), [refreshKey])
  const rolesResult = useAsync(() => listRoles(), [])

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">User Management</h1>
        <p className="mt-1 text-sm text-slate-500">
          Admin only. Create accounts, manage roles, and activate/deactivate users.
        </p>
      </div>

      <CreateUserForm onCreated={() => setRefreshKey((k) => k + 1)} />

      {(usersResult.status === 'loading' || rolesResult.status === 'loading') && (
        <LoadingSpinner label="Loading users…" />
      )}
      {usersResult.status === 'error' && (
        <ErrorMessage message={usersResult.error} onRetry={usersResult.reload} />
      )}
      {rolesResult.status === 'error' && (
        <ErrorMessage message={rolesResult.error} onRetry={rolesResult.reload} />
      )}
      {usersResult.status === 'success' &&
        rolesResult.status === 'success' &&
        (usersResult.data.length === 0 ? (
          <EmptyState title="No users yet" />
        ) : (
          <UsersTable
            users={usersResult.data}
            roles={rolesResult.data}
            currentUserId={currentUser?.id ?? null}
            onChanged={() => setRefreshKey((k) => k + 1)}
          />
        ))}
    </div>
  )
}

function CreateUserForm({ onCreated }: { onCreated: () => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await createUser(email, password, fullName)
      setEmail('')
      setPassword('')
      setFullName('')
      onCreated()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to create user.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
      aria-label="Create user"
    >
      <h2 className="text-sm font-semibold text-slate-900">Create user</h2>
      <p className="mt-1 text-xs text-slate-500">New users start with the Viewer role.</p>
      <div className="mt-3 flex flex-wrap items-end gap-3">
        <Field label="Full name">
          <input
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className={inputClass}
          />
        </Field>
        <Field label="Email">
          <input
            required
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={inputClass}
          />
        </Field>
        <Field label="Password">
          <input
            required
            type="password"
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputClass}
          />
        </Field>
        <button
          type="submit"
          disabled={submitting}
          className="rounded-md bg-accent-600 px-4 py-2 text-sm font-medium text-white hover:bg-accent-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {submitting ? 'Creating…' : 'Create'}
        </button>
      </div>
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {error}
        </p>
      )}
    </form>
  )
}

function UsersTable({
  users,
  roles,
  currentUserId,
  onChanged,
}: {
  users: UserAdmin[]
  roles: RoleInfo[]
  currentUserId: string | null
  onChanged: () => void
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">User</th>
            <th className="px-4 py-3">Roles</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Created</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {users.map((user) => (
            <UserRow
              key={user.id}
              user={user}
              roles={roles}
              isSelf={user.id === currentUserId}
              onChanged={onChanged}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function UserRow({
  user,
  roles,
  isSelf,
  onChanged,
}: {
  user: UserAdmin
  roles: RoleInfo[]
  isSelf: boolean
  onChanged: () => void
}) {
  const [selectedRoles, setSelectedRoles] = useState<string[]>(user.roles)
  const [busy, setBusy] = useState(false)
  const [rowError, setRowError] = useState<string | null>(null)

  const rolesChanged =
    selectedRoles.length !== user.roles.length || !selectedRoles.every((r) => user.roles.includes(r))

  function toggleRole(name: string) {
    setSelectedRoles((current) =>
      current.includes(name) ? current.filter((r) => r !== name) : [...current, name],
    )
  }

  async function runAction(action: () => Promise<unknown>) {
    setBusy(true)
    setRowError(null)
    try {
      await action()
      onChanged()
    } catch (err) {
      setRowError(err instanceof ApiError ? err.message : 'Action failed.')
      setBusy(false)
    }
  }

  return (
    <tr className="hover:bg-slate-50">
      <td className="px-4 py-3">
        <div className="font-medium text-slate-800">{user.full_name}</div>
        <div className="text-xs text-slate-400">
          {user.email} {isSelf && '(you)'}
        </div>
        {rowError && <div className="mt-1 text-xs text-red-600">{rowError}</div>}
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-col gap-1">
          {roles.map((role) => (
            <label key={role.id} className="flex items-center gap-2 text-xs text-slate-600">
              <input
                type="checkbox"
                disabled={isSelf || busy}
                checked={selectedRoles.includes(role.name)}
                onChange={() => toggleRole(role.name)}
              />
              {role.name}
            </label>
          ))}
          {rolesChanged && !isSelf && (
            <button
              type="button"
              disabled={busy}
              onClick={() => runAction(() => assignRoles(user.id, selectedRoles))}
              className="mt-1 self-start rounded-md bg-accent-600 px-2 py-1 text-xs font-medium text-white hover:bg-accent-700"
            >
              Save roles
            </button>
          )}
        </div>
      </td>
      <td className="px-4 py-3">
        <span
          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${
            user.is_active
              ? 'bg-emerald-50 text-emerald-700 ring-emerald-200'
              : 'bg-slate-100 text-slate-500 ring-slate-200'
          }`}
        >
          {user.is_active ? 'Active' : 'Deactivated'}
        </span>
      </td>
      <td className="px-4 py-3 text-slate-500">{new Date(user.created_at).toLocaleDateString()}</td>
      <td className="px-4 py-3 text-right">
        <div className="flex justify-end gap-2">
          <button
            type="button"
            disabled={isSelf || busy}
            onClick={() => runAction(() => updateUser(user.id, { isActive: !user.is_active }))}
            className="text-xs font-medium text-slate-500 hover:text-accent-600 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {user.is_active ? 'Deactivate' : 'Activate'}
          </button>
          <button
            type="button"
            disabled={isSelf || busy}
            onClick={() => runAction(() => deleteUser(user.id))}
            className="text-xs font-medium text-slate-400 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Delete
          </button>
        </div>
      </td>
    </tr>
  )
}
