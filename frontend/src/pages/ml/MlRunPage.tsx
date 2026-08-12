import { Link, useParams } from 'react-router-dom'
import { getMlRun } from '../../api/client'
import {
  isAnomalyResults,
  isClassificationResults,
  isForecastResults,
  isSegmentationResults,
} from '../../api/types'
import { TASK_META } from '../../components/ml/taskMeta'
import { ClassificationResultsView } from '../../components/ml/ClassificationResultsView'
import { ForecastResultsView } from '../../components/ml/ForecastResultsView'
import { SegmentationResultsView } from '../../components/ml/SegmentationResultsView'
import { AnomalyResultsView } from '../../components/ml/AnomalyResultsView'
import { RegisterVersionAction } from '../../components/mlops/RegisterVersionAction'
import { LoadingSpinner } from '../../components/common/LoadingSpinner'
import { ErrorMessage } from '../../components/common/ErrorMessage'
import { useAsync } from '../../hooks/useAsync'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function MlRunPage() {
  const { runId } = useParams<{ runId: string }>()
  const result = useAsync(() => getMlRun(runId!), [runId])

  if (!runId) return null
  if (result.status === 'loading') return <LoadingSpinner label="Loading run…" />
  if (result.status === 'error') return <ErrorMessage message={result.error} onRetry={result.reload} />

  const runResults = result.data
  const { run } = runResults
  const meta = TASK_META[run.task_type]

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link to="/ml" className="text-xs font-medium text-accent-600 hover:underline">
          &larr; Back to ML
        </Link>
        <div className="mt-2 flex items-center gap-3">
          <h1 className="text-xl font-semibold text-slate-900">{meta.label}</h1>
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
            {run.model_name}
          </span>
        </div>
        <p className="mt-1 text-sm text-slate-500">
          Trained {formatDate(run.created_at)} ·{' '}
          <Link to={`/datasets/${run.dataset_id}`} className="text-accent-600 hover:underline">
            View source dataset
          </Link>
        </p>
      </div>

      {isClassificationResults(runResults) && (
        <ClassificationResultsView runId={run.id} results={runResults.results} />
      )}
      {isForecastResults(runResults) && (
        <ForecastResultsView runId={run.id} results={runResults.results} />
      )}
      {isSegmentationResults(runResults) && (
        <SegmentationResultsView runId={run.id} results={runResults.results} />
      )}
      {isAnomalyResults(runResults) && (
        <AnomalyResultsView runId={run.id} results={runResults.results} />
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">Model registry</h2>
        <RegisterVersionAction runId={run.id} />
      </section>
    </div>
  )
}
