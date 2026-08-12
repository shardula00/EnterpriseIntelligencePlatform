import { useState } from 'react'
import { Link } from 'react-router-dom'
import { listModelVersions } from '../../api/client'
import type { LifecycleStatus } from '../../api/types'
import { TASK_META } from '../../components/ml/taskMeta'
import { LifecycleBadge } from '../../components/mlops/LifecycleBadge'
import { LoadingSpinner } from '../../components/common/LoadingSpinner'
import { ErrorMessage } from '../../components/common/ErrorMessage'
import { EmptyState } from '../../components/common/EmptyState'
import { useAsync } from '../../hooks/useAsync'

const STATUS_OPTIONS: (LifecycleStatus | '')[] = ['', 'candidate', 'staging', 'production', 'archived']

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function ModelRegistryPage() {
  const [statusFilter, setStatusFilter] = useState<LifecycleStatus | ''>('')
  const versions = useAsync(
    () => listModelVersions(statusFilter ? { status: statusFilter } : {}),
    [statusFilter],
  )

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Model Registry</h1>
          <p className="mt-1 text-sm text-slate-500">
            Every model version registered from a training run, with its current lifecycle state.
            Register a version from a run's results page under{' '}
            <Link to="/ml/runs" className="text-accent-600 hover:underline">
              ML run history
            </Link>
            .
          </p>
        </div>
        <Link
          to="/mlops/alerts"
          className="shrink-0 rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100"
        >
          View monitoring alerts
        </Link>
      </div>

      <div className="flex items-end gap-3">
        <label className="text-sm">
          <span className="mb-1 block font-medium text-slate-700">Status</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as LifecycleStatus | '')}
            className="rounded-md border border-slate-300 px-2 py-1.5 text-sm text-slate-700 focus:border-accent-500 focus:outline-none"
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s === '' ? 'All' : s}
              </option>
            ))}
          </select>
        </label>
      </div>

      {versions.status === 'loading' && <LoadingSpinner label="Loading model registry…" />}
      {versions.status === 'error' && (
        <ErrorMessage message={versions.error} onRetry={versions.reload} />
      )}
      {versions.status === 'success' &&
        (versions.data.length === 0 ? (
          <EmptyState
            title="No model versions registered yet"
            description="Train a model, then register its run as a version from the run's results page."
          />
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Task</th>
                  <th className="px-4 py-3">Version</th>
                  <th className="px-4 py-3">Algorithm</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Registered</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {versions.data.map((version) => (
                  <tr key={version.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <Link
                        to={`/mlops/versions/${version.id}`}
                        className="font-medium text-accent-600 hover:underline"
                      >
                        {TASK_META[version.task_type].shortLabel}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-slate-700">v{version.version_number}</td>
                    <td className="px-4 py-3 text-slate-600">{version.model_name}</td>
                    <td className="px-4 py-3">
                      <LifecycleBadge status={version.status} />
                    </td>
                    <td className="px-4 py-3 text-slate-500">{formatDate(version.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
    </div>
  )
}
