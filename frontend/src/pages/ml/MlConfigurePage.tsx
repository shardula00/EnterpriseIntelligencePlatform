import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { getColumns, getDataset, getMlSuitability } from '../../api/client'
import { TASK_META, isMlTaskType } from '../../components/ml/taskMeta'
import { ClassificationConfigForm } from '../../components/ml/ClassificationConfigForm'
import { ForecastConfigForm } from '../../components/ml/ForecastConfigForm'
import { SegmentationConfigForm } from '../../components/ml/SegmentationConfigForm'
import { AnomalyConfigForm } from '../../components/ml/AnomalyConfigForm'
import { LoadingSpinner } from '../../components/common/LoadingSpinner'
import { ErrorMessage } from '../../components/common/ErrorMessage'
import { useAsync } from '../../hooks/useAsync'
import { usePermission } from '../../hooks/usePermission'

async function loadConfigureData(datasetId: string, taskType: string) {
  const [dataset, columns, suitability] = await Promise.all([
    getDataset(datasetId),
    getColumns(datasetId),
    getMlSuitability(datasetId),
  ])
  const check = suitability.tasks.find((t) => t.task_type === taskType)
  if (!check) throw new Error(`Backend did not report suitability for task "${taskType}".`)
  return { dataset, columns, check }
}

export function MlConfigurePage() {
  const { taskType, datasetId } = useParams<{ taskType: string; datasetId: string }>()
  const navigate = useNavigate()
  const canTrain = usePermission('ml:train')
  const result = useAsync(
    () =>
      datasetId && taskType
        ? loadConfigureData(datasetId, taskType)
        : Promise.reject(new Error('Missing dataset or task.')),
    [datasetId, taskType],
  )

  if (!isMlTaskType(taskType) || !datasetId) {
    return <Navigate to="/ml" replace />
  }

  const meta = TASK_META[taskType]

  function handleTrained(runId: string) {
    navigate(`/ml/runs/${runId}`)
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link
          to={`/ml/${taskType}`}
          className="text-xs font-medium text-accent-600 hover:underline"
        >
          &larr; Back to dataset selection
        </Link>
        <h1 className="mt-2 text-xl font-semibold text-slate-900">Configure: {meta.label}</h1>
      </div>

      {!canTrain && (
        <ErrorMessage message="Training a model requires Analyst or Admin access." />
      )}

      {canTrain && result.status === 'loading' && <LoadingSpinner label="Loading dataset details…" />}
      {canTrain && result.status === 'error' && (
        <ErrorMessage message={result.error} onRetry={result.reload} />
      )}
      {canTrain &&
        result.status === 'success' &&
        (!result.data.check.suitable ? (
          <ErrorMessage
            message={`"${result.data.dataset.name}" is not suitable for ${meta.shortLabel}: ${result.data.check.reasons.join(' ')}`}
          />
        ) : (
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <p className="mb-5 text-sm text-slate-500">
              Dataset: <span className="font-medium text-slate-700">{result.data.dataset.name}</span>{' '}
              ({result.data.dataset.row_count.toLocaleString()} rows)
            </p>
            {taskType === 'classification' && (
              <ClassificationConfigForm
                datasetId={datasetId}
                columns={result.data.columns.map((c) => c.column_name)}
                check={result.data.check}
                onTrained={handleTrained}
              />
            )}
            {taskType === 'forecasting' && (
              <ForecastConfigForm datasetId={datasetId} check={result.data.check} onTrained={handleTrained} />
            )}
            {taskType === 'segmentation' && (
              <SegmentationConfigForm
                datasetId={datasetId}
                columns={result.data.columns.map((c) => c.column_name)}
                check={result.data.check}
                onTrained={handleTrained}
              />
            )}
            {taskType === 'anomaly_detection' && (
              <AnomalyConfigForm
                datasetId={datasetId}
                columns={result.data.columns.map((c) => c.column_name)}
                check={result.data.check}
                onTrained={handleTrained}
              />
            )}
          </div>
        ))}
    </div>
  )
}
