import { useState } from 'react'
import { listDatasets, runPerformanceCheck } from '../../api/client'
import type { PerformanceCheck } from '../../api/types'
import { useAsync } from '../../hooks/useAsync'
import { usePermission } from '../../hooks/usePermission'
import { ErrorMessage } from '../common/ErrorMessage'
import { LoadingSpinner } from '../common/LoadingSpinner'

const STATUS_STYLES: Record<PerformanceCheck['status'], string> = {
  stable: 'bg-emerald-100 text-emerald-700',
  warning: 'bg-amber-100 text-amber-700',
  degraded: 'bg-red-100 text-red-700',
  not_applicable: 'bg-slate-100 text-slate-600',
}

/** Compares a model version's recorded training-time metric against the
 * same metric recomputed on a new dataset - never retrains anything, only
 * ever reports a status. Distinguishes real ground-truth performance
 * (classification/forecasting) from an unsupervised proxy signal
 * (segmentation/anomaly detection - see app/mlops/monitoring.py). */
export function PerformanceCheckPanel({
  versionId,
  onChecked,
}: {
  versionId: string
  /** Called after a successful check, e.g. so a parent's separately-fetched
   * monitoring event list can refresh to include the event this check just
   * recorded, without requiring a full page reload. */
  onChecked?: () => void
}) {
  const canEvaluate = usePermission('mlops:evaluate')
  const datasets = useAsync(() => listDatasets(), [])
  const [datasetId, setDatasetId] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'error' | 'success'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<PerformanceCheck | null>(null)

  async function handleRun() {
    if (!datasetId) return
    setStatus('loading')
    setError(null)
    try {
      const response = await runPerformanceCheck(versionId, datasetId)
      setResult(response)
      setStatus('success')
      onChecked?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setStatus('error')
    }
  }

  if (!canEvaluate) {
    return (
      <p className="text-xs text-slate-400">
        Running a performance check requires Analyst or Admin access.
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="mb-1 block font-medium text-slate-700">Evaluate against dataset</span>
          {datasets.status === 'loading' && <LoadingSpinner label="Loading datasets…" />}
          {datasets.status === 'error' && (
            <ErrorMessage message={datasets.error} onRetry={datasets.reload} />
          )}
          {datasets.status === 'success' && (
            <select
              value={datasetId}
              onChange={(e) => setDatasetId(e.target.value)}
              className="rounded-md border border-slate-300 px-2 py-1.5 text-sm text-slate-700 focus:border-accent-500 focus:outline-none"
            >
              <option value="">Select a dataset…</option>
              {datasets.data.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          )}
        </label>
        <button
          type="button"
          onClick={handleRun}
          disabled={!datasetId || status === 'loading'}
          className="rounded-md bg-accent-600 px-4 py-2 text-sm font-medium text-white hover:bg-accent-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {status === 'loading' ? 'Checking…' : 'Run performance check'}
        </button>
      </div>

      {status === 'error' && error && <ErrorMessage message={error} onRetry={handleRun} />}

      {status === 'success' && result && (
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex items-center gap-3">
            <span
              className={`rounded-full px-2.5 py-1 text-xs font-medium capitalize ${STATUS_STYLES[result.status]}`}
            >
              {result.status.replace('_', ' ')}
            </span>
            {!result.ground_truth_available && (
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-500">
                No ground truth - proxy signal only
              </span>
            )}
          </div>

          <div className="mt-3 flex flex-wrap gap-3">
            <div className="rounded-lg border border-slate-200 px-4 py-3">
              <p className="text-xs uppercase tracking-wide text-slate-400">{result.primary_metric}</p>
              <p className="text-lg font-semibold text-slate-900">baseline: {result.baseline_value}</p>
            </div>
            <div className="rounded-lg border border-slate-200 px-4 py-3">
              <p className="text-xs uppercase tracking-wide text-slate-400">{result.primary_metric}</p>
              <p className="text-lg font-semibold text-slate-900">current: {result.current_value}</p>
            </div>
            <div className="rounded-lg border border-slate-200 px-4 py-3">
              <p className="text-xs uppercase tracking-wide text-slate-400">Relative change</p>
              <p className="text-lg font-semibold text-slate-900">
                {result.relative_change != null ? `${Math.round(result.relative_change * 100)}%` : '—'}
              </p>
            </div>
          </div>

          <p className="mt-3 text-xs text-slate-500">{result.explanation}</p>
          <p className="mt-1 text-xs text-slate-400">
            Thresholds: warning &ge; {Math.round(result.warning_threshold * 100)}% relative change,
            degraded &ge; {Math.round(result.severe_threshold * 100)}%.
          </p>

          {Object.keys(result.extra_metrics ?? {}).length > 0 && (
            <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500">
              {Object.entries(result.extra_metrics ?? {}).map(([name, value]) => (
                <span key={name}>
                  {name}: <span className="font-medium text-slate-700">{value}</span>
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
