import { Link } from 'react-router-dom'
import { listMlRuns } from '../../api/client'
import { TASK_META } from '../../components/ml/taskMeta'
import { LoadingSpinner } from '../../components/common/LoadingSpinner'
import { ErrorMessage } from '../../components/common/ErrorMessage'
import { EmptyState } from '../../components/common/EmptyState'
import { useAsync } from '../../hooks/useAsync'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function MlRunsHistoryPage() {
  const runs = useAsync(() => listMlRuns({}), [])

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link to="/ml" className="text-xs font-medium text-accent-600 hover:underline">
          &larr; Back to ML
        </Link>
        <h1 className="mt-2 text-xl font-semibold text-slate-900">ML run history</h1>
        <p className="mt-1 text-sm text-slate-500">Every model trained on this platform.</p>
      </div>

      {runs.status === 'loading' && <LoadingSpinner label="Loading runs…" />}
      {runs.status === 'error' && <ErrorMessage message={runs.error} onRetry={runs.reload} />}
      {runs.status === 'success' &&
        (runs.data.length === 0 ? (
          <EmptyState title="No ML runs yet" description="Train your first model from the ML section." />
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Task</th>
                  <th className="px-4 py-3">Model</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Trained</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {runs.data.map((run) => (
                  <tr key={run.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <Link
                        to={`/ml/runs/${run.id}`}
                        className="font-medium text-accent-600 hover:underline"
                      >
                        {TASK_META[run.task_type].shortLabel}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-slate-700">{run.model_name}</td>
                    <td className="px-4 py-3 text-slate-500">{run.status}</td>
                    <td className="px-4 py-3 text-slate-500">{formatDate(run.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
    </div>
  )
}
