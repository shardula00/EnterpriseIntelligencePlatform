import { Link } from 'react-router-dom'
import { listMlRuns } from '../../api/client'
import { TASK_META, TASK_TYPES } from '../../components/ml/taskMeta'
import { LoadingSpinner } from '../../components/common/LoadingSpinner'
import { ErrorMessage } from '../../components/common/ErrorMessage'
import { EmptyState } from '../../components/common/EmptyState'
import { useAsync } from '../../hooks/useAsync'
import { usePermission } from '../../hooks/usePermission'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function MlTaskSelectionPage() {
  const canTrain = usePermission('ml:train')
  const runs = useAsync(() => listMlRuns({}), [])

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Machine Learning</h1>
        <p className="mt-1 text-sm text-slate-500">
          Train and evaluate a classical ML model on one of your datasets.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {TASK_TYPES.map((taskType) => {
          const meta = TASK_META[taskType]
          return (
            <Link
              key={taskType}
              to={canTrain ? `/ml/${taskType}` : '#'}
              aria-disabled={!canTrain}
              className={`rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition ${
                canTrain ? 'hover:border-accent-300 hover:shadow-md' : 'cursor-not-allowed opacity-60'
              }`}
              onClick={(e) => {
                if (!canTrain) e.preventDefault()
              }}
            >
              <h2 className="text-sm font-semibold text-slate-900">{meta.label}</h2>
              <p className="mt-1 text-sm text-slate-500">{meta.description}</p>
            </Link>
          )
        })}
      </div>
      {!canTrain && (
        <p className="text-xs text-slate-400">
          Training requires Analyst or Admin access. You can still view past run results below.
        </p>
      )}

      <div>
        <h2 className="text-sm font-semibold text-slate-900">Recent runs</h2>
        <div className="mt-3">
          {runs.status === 'loading' && <LoadingSpinner label="Loading recent runs…" />}
          {runs.status === 'error' && <ErrorMessage message={runs.error} onRetry={runs.reload} />}
          {runs.status === 'success' &&
            (runs.data.length === 0 ? (
              <EmptyState
                title="No ML runs yet"
                description="Pick a task above and train your first model."
              />
            ) : (
              <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
                <table className="min-w-full divide-y divide-slate-200 text-sm">
                  <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-4 py-3">Task</th>
                      <th className="px-4 py-3">Model</th>
                      <th className="px-4 py-3">Trained</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {runs.data.slice(0, 10).map((run) => (
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
                        <td className="px-4 py-3 text-slate-500">{formatDate(run.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
        </div>
      </div>
    </div>
  )
}
