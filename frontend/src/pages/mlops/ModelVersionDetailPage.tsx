import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { archiveModelVersion, getModelVersion, listMonitoringEvents, promoteModelVersion } from '../../api/client'
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
import { LifecycleBadge } from '../../components/mlops/LifecycleBadge'
import { DriftCheckPanel } from '../../components/mlops/DriftCheckPanel'
import { PerformanceCheckPanel } from '../../components/mlops/PerformanceCheckPanel'
import { MonitoringEventList } from '../../components/mlops/MonitoringEventList'
import { LoadingSpinner } from '../../components/common/LoadingSpinner'
import { ErrorMessage } from '../../components/common/ErrorMessage'
import { useAsync } from '../../hooks/useAsync'
import { usePermission } from '../../hooks/usePermission'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

function LifecycleActions({
  versionId,
  status,
  onChanged,
}: {
  versionId: string
  status: string
  onChanged: () => void
}) {
  const canPromote = usePermission('mlops:promote')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handlePromote(target: 'staging' | 'production') {
    setBusy(true)
    setError(null)
    try {
      await promoteModelVersion(versionId, target)
      onChanged()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleArchive() {
    setBusy(true)
    setError(null)
    try {
      await archiveModelVersion(versionId)
      onChanged()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  if (!canPromote) {
    return (
      <p className="text-xs text-slate-400">
        Promoting or archiving a model version requires Admin access.
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2">
        {status === 'candidate' && (
          <button
            type="button"
            onClick={() => handlePromote('staging')}
            disabled={busy}
            className="rounded-md bg-accent-600 px-4 py-2 text-sm font-medium text-white hover:bg-accent-700 disabled:opacity-50"
          >
            Promote to staging
          </button>
        )}
        {status === 'staging' && (
          <button
            type="button"
            onClick={() => handlePromote('production')}
            disabled={busy}
            className="rounded-md bg-accent-600 px-4 py-2 text-sm font-medium text-white hover:bg-accent-700 disabled:opacity-50"
          >
            Promote to production
          </button>
        )}
        {(status === 'candidate' || status === 'staging' || status === 'production') && (
          <button
            type="button"
            onClick={handleArchive}
            disabled={busy}
            className="rounded-md border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
          >
            Archive
          </button>
        )}
        {status === 'archived' && (
          <p className="text-xs text-slate-400">
            Archived is terminal - register a new version (e.g. after retraining) instead.
          </p>
        )}
      </div>
      {error && <ErrorMessage message={error} />}
    </div>
  )
}

export function ModelVersionDetailPage() {
  const { versionId } = useParams<{ versionId: string }>()
  const detail = useAsync(() => getModelVersion(versionId!), [versionId])
  const events = useAsync(
    () => (versionId ? listMonitoringEvents({ modelVersionId: versionId }) : Promise.resolve([])),
    [versionId],
  )

  if (!versionId) return null
  if (detail.status === 'loading') return <LoadingSpinner label="Loading model version…" />
  if (detail.status === 'error') return <ErrorMessage message={detail.error} onRetry={detail.reload} />

  const { version, run: runResults } = detail.data
  const meta = TASK_META[version.task_type]

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link to="/mlops" className="text-xs font-medium text-accent-600 hover:underline">
          &larr; Back to model registry
        </Link>
        <div className="mt-2 flex items-center gap-3">
          <h1 className="text-xl font-semibold text-slate-900">
            {meta.label} - v{version.version_number}
          </h1>
          <LifecycleBadge status={version.status} />
        </div>
        <p className="mt-1 text-sm text-slate-500">
          {version.model_name} ·{' '}
          <Link to={`/ml/runs/${version.ml_run_id}`} className="text-accent-600 hover:underline">
            View training run
          </Link>{' '}
          ·{' '}
          <Link to={`/datasets/${version.dataset_id}`} className="text-accent-600 hover:underline">
            View dataset
          </Link>
        </p>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">Version &amp; lifecycle</h2>
        <div className="mb-4 flex flex-wrap gap-3 text-sm text-slate-600">
          <span>
            Artifact checksum:{' '}
            <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">
              {version.artifact_checksum.slice(0, 16)}…
            </code>
          </span>
          <span>Created {formatDate(version.created_at)}</span>
          {version.promoted_at && <span>Last transitioned {formatDate(version.promoted_at)}</span>}
        </div>
        <LifecycleActions
          versionId={version.id}
          status={version.status}
          onChanged={() => {
            detail.reload()
          }}
        />
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-slate-900">Training run results</h2>
        {isClassificationResults(runResults) && (
          <ClassificationResultsView runId={runResults.run.id} results={runResults.results} />
        )}
        {isForecastResults(runResults) && (
          <ForecastResultsView runId={runResults.run.id} results={runResults.results} />
        )}
        {isSegmentationResults(runResults) && (
          <SegmentationResultsView runId={runResults.run.id} results={runResults.results} />
        )}
        {isAnomalyResults(runResults) && (
          <AnomalyResultsView runId={runResults.run.id} results={runResults.results} />
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">Data drift monitoring</h2>
        <DriftCheckPanel versionId={version.id} onChecked={events.reload} />
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">Performance monitoring</h2>
        <PerformanceCheckPanel versionId={version.id} onChecked={events.reload} />
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-slate-900">Monitoring history for this version</h2>
        {events.status === 'loading' && <LoadingSpinner label="Loading monitoring history…" />}
        {events.status === 'error' && <ErrorMessage message={events.error} onRetry={events.reload} />}
        {events.status === 'success' && <MonitoringEventList events={events.data} />}
      </section>
    </div>
  )
}
