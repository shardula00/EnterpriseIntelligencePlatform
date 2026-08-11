import { useState } from 'react'
import { listAuditLogs } from '../../api/client'
import { useAsync } from '../../hooks/useAsync'
import { LoadingSpinner } from '../../components/common/LoadingSpinner'
import { ErrorMessage } from '../../components/common/ErrorMessage'
import { EmptyState } from '../../components/common/EmptyState'

const PAGE_SIZE = 20

// Mirrors app/audit/service.py's AuditAction constants - a fixed,
// documented set, not user-entered free text.
const ACTIONS = [
  'user.registered',
  'auth.login.success',
  'auth.login.failed',
  'auth.logout',
  'dataset.uploaded',
  'dataset.deleted',
  'user.created',
  'user.updated',
  'user.activated',
  'user.deactivated',
  'user.deleted',
  'user.role_changed',
]

export function AuditLogPage() {
  const [offset, setOffset] = useState(0)
  const [action, setAction] = useState('')

  const result = useAsync(
    () => listAuditLogs({ limit: PAGE_SIZE, offset, action: action || undefined }),
    [offset, action],
  )

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Audit Log</h1>
        <p className="mt-1 text-sm text-slate-500">
          Admin/auditor only. Every security- and administration-relevant action, most recent first.
        </p>
      </div>

      <div className="flex items-end gap-3">
        <label className="text-xs text-slate-500">
          <span className="mb-1 block font-medium">Action</span>
          <select
            value={action}
            onChange={(e) => {
              setAction(e.target.value)
              setOffset(0)
            }}
            className="rounded-md border border-slate-300 px-2 py-1.5 text-sm text-slate-700 focus:border-accent-500 focus:outline-none"
          >
            <option value="">All actions</option>
            {ACTIONS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
      </div>

      {result.status === 'loading' && <LoadingSpinner label="Loading audit log…" />}
      {result.status === 'error' && <ErrorMessage message={result.error} onRetry={result.reload} />}
      {result.status === 'success' &&
        (result.data.items.length === 0 ? (
          <EmptyState title="No audit events" description="Nothing matches this filter yet." />
        ) : (
          <>
            <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Timestamp</th>
                    <th className="px-4 py-3">User</th>
                    <th className="px-4 py-3">Action</th>
                    <th className="px-4 py-3">Resource</th>
                    <th className="px-4 py-3">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {result.data.items.map((entry) => (
                    <tr key={entry.id} className="hover:bg-slate-50 align-top">
                      <td className="whitespace-nowrap px-4 py-3 text-slate-500">
                        {new Date(entry.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-slate-700">{entry.user_email ?? '—'}</td>
                      <td className="px-4 py-3">
                        <span className="inline-flex rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                          {entry.action}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-500">
                        {entry.resource_type ? (
                          <>
                            {entry.resource_type}
                            <div className="text-xs text-slate-400">{entry.resource_id}</div>
                          </>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className="max-w-xs px-4 py-3 text-xs text-slate-500">
                        {entry.event_metadata ? (
                          <pre className="whitespace-pre-wrap break-words">
                            {JSON.stringify(entry.event_metadata, null, 2)}
                          </pre>
                        ) : (
                          '—'
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex items-center justify-between text-sm text-slate-500">
              <span>
                Showing {offset + 1}-{offset + result.data.items.length} of {result.data.total}
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={offset === 0}
                  onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
                  className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Previous
                </button>
                <button
                  type="button"
                  disabled={offset + PAGE_SIZE >= result.data.total}
                  onClick={() => setOffset((o) => o + PAGE_SIZE)}
                  className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          </>
        ))}
    </div>
  )
}
