import { useState } from 'react'
import { listDatasets, runDriftCheck } from '../../api/client'
import type { DriftResult } from '../../api/types'
import { useAsync } from '../../hooks/useAsync'
import { usePermission } from '../../hooks/usePermission'
import { ErrorMessage } from '../common/ErrorMessage'
import { LoadingSpinner } from '../common/LoadingSpinner'

const STATUS_STYLES: Record<DriftResult['overall_status'], string> = {
  stable: 'bg-emerald-100 text-emerald-700',
  warning: 'bg-amber-100 text-amber-700',
  drift: 'bg-red-100 text-red-700',
  unknown: 'bg-slate-100 text-slate-600',
}

/** Lets an authorized user evaluate a model version against a new/reference
 * dataset for data drift - never retrains anything, only ever reports a
 * status (see app/mlops/drift.py's module docstring for the PSI
 * methodology and threshold meaning shown below). */
export function DriftCheckPanel({
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
  const [result, setResult] = useState<DriftResult | null>(null)

  async function handleRun() {
    if (!datasetId) return
    setStatus('loading')
    setError(null)
    try {
      const response = await runDriftCheck(versionId, datasetId)
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
      <p className="text-xs text-slate-400">Running a drift check requires Analyst or Admin access.</p>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="mb-1 block font-medium text-slate-700">Compare against dataset</span>
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
          {status === 'loading' ? 'Checking…' : 'Run drift check'}
        </button>
      </div>

      {status === 'error' && error && <ErrorMessage message={error} onRetry={handleRun} />}

      {status === 'success' && result && (
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex items-center gap-3">
            <span
              className={`rounded-full px-2.5 py-1 text-xs font-medium capitalize ${STATUS_STYLES[result.overall_status]}`}
            >
              {result.overall_status}
            </span>
            <p className="text-sm text-slate-600">
              {result.drifted_feature_count} drifted, {result.warning_feature_count} moderate, of{' '}
              {result.total_features_checked} feature(s) checked.
            </p>
          </div>
          <p className="mt-2 text-xs text-slate-500">{result.explanation}</p>
          <p className="mt-1 text-xs text-slate-400">
            Thresholds: warning &ge; {result.warning_threshold}, drift &ge; {result.severe_threshold}{' '}
            (PSI - Population Stability Index).
          </p>

          <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2">Feature</th>
                  <th className="px-3 py-2">Type</th>
                  <th className="px-3 py-2">Statistic</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Explanation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {result.features.map((f) => (
                  <tr key={f.feature}>
                    <td className="px-3 py-2 font-medium text-slate-800">{f.feature}</td>
                    <td className="px-3 py-2 text-slate-500">{f.feature_type}</td>
                    <td className="px-3 py-2 text-slate-600">{f.statistic ?? '—'}</td>
                    <td className="px-3 py-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${STATUS_STYLES[f.status]}`}
                      >
                        {f.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-xs text-slate-500">{f.explanation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
