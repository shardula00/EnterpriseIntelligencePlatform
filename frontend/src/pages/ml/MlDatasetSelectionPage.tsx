import { Link, Navigate, useParams } from 'react-router-dom'
import { getMlSuitability, listDatasets } from '../../api/client'
import type { DatasetSummary, TaskSuitability } from '../../api/types'
import { TASK_META, isMlTaskType } from '../../components/ml/taskMeta'
import { LoadingSpinner } from '../../components/common/LoadingSpinner'
import { ErrorMessage } from '../../components/common/ErrorMessage'
import { EmptyState } from '../../components/common/EmptyState'
import { useAsync } from '../../hooks/useAsync'

interface DatasetWithSuitability {
  dataset: DatasetSummary
  check: TaskSuitability
}

/** One suitability call per dataset (each call already reports all 4
 * tasks at once - see app/ml/service.py's get_dataset_suitability), then
 * pick out the single task this page cares about. */
async function loadDatasetsWithSuitability(taskType: string): Promise<DatasetWithSuitability[]> {
  const datasets = await listDatasets()
  return Promise.all(
    datasets.map(async (dataset) => {
      const result = await getMlSuitability(dataset.id)
      const check = result.tasks.find((t) => t.task_type === taskType)
      if (!check) throw new Error(`Backend did not report suitability for task "${taskType}".`)
      return { dataset, check }
    }),
  )
}

export function MlDatasetSelectionPage() {
  const { taskType } = useParams<{ taskType: string }>()
  const rows = useAsync(
    () => (taskType ? loadDatasetsWithSuitability(taskType) : Promise.resolve([])),
    [taskType],
  )

  if (!isMlTaskType(taskType)) {
    return <Navigate to="/ml" replace />
  }

  const meta = TASK_META[taskType]

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link to="/ml" className="text-xs font-medium text-accent-600 hover:underline">
          &larr; Back to task selection
        </Link>
        <h1 className="mt-2 text-xl font-semibold text-slate-900">{meta.label}</h1>
        <p className="mt-1 text-sm text-slate-500">
          Choose a dataset to train on. Datasets that don&apos;t meet this task&apos;s
          requirements are shown with the reason why.
        </p>
      </div>

      {rows.status === 'loading' && <LoadingSpinner label="Checking dataset suitability…" />}
      {rows.status === 'error' && <ErrorMessage message={rows.error} onRetry={rows.reload} />}
      {rows.status === 'success' &&
        (rows.data.length === 0 ? (
          <EmptyState
            title="No datasets yet"
            description="Upload a dataset first from the Datasets page."
          />
        ) : (
          <div className="flex flex-col gap-3">
            {rows.data.map(({ dataset, check }) => (
              <DatasetSuitabilityRow
                key={dataset.id}
                dataset={dataset}
                taskType={taskType}
                check={check}
              />
            ))}
          </div>
        ))}
    </div>
  )
}

function DatasetSuitabilityRow({
  dataset,
  taskType,
  check,
}: {
  dataset: DatasetSummary
  taskType: string
  check: TaskSuitability
}) {
  const content = (
    <div
      className={`flex items-start justify-between gap-4 rounded-xl border bg-white p-4 shadow-sm ${
        check.suitable
          ? 'border-slate-200 hover:border-accent-300 hover:shadow-md'
          : 'border-slate-200 opacity-75'
      }`}
    >
      <div>
        <p className="font-medium text-slate-900">{dataset.name}</p>
        <p className="text-xs text-slate-400">
          {dataset.row_count.toLocaleString()} rows · {dataset.column_count} columns
        </p>
        {!check.suitable && (
          <ul className="mt-2 list-inside list-disc text-xs text-red-600">
            {check.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        )}
      </div>
      <span
        className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${
          check.suitable ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'
        }`}
      >
        {check.suitable ? 'Suitable' : 'Not suitable'}
      </span>
    </div>
  )

  if (!check.suitable) {
    return content
  }

  return (
    <Link to={`/ml/${taskType}/${dataset.id}`} className="block">
      {content}
    </Link>
  )
}
