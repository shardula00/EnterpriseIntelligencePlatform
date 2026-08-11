import { Link } from 'react-router-dom'
import type { DatasetSummary } from '../../api/types'
import { usePermission } from '../../hooks/usePermission'
import { EmptyState } from '../common/EmptyState'
import { QualityScoreBadge } from './QualityScoreBadge'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

export function DatasetList({
  datasets,
  onDelete,
}: {
  datasets: DatasetSummary[]
  onDelete: (dataset: DatasetSummary) => void
}) {
  // UX only - the backend independently rejects DELETE without
  // dataset:delete regardless of whether this button is shown.
  const canDelete = usePermission('dataset:delete')

  if (datasets.length === 0) {
    return (
      <EmptyState
        title="No datasets yet"
        description="Upload a CSV, Excel, or JSON file above to get started."
      />
    )
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">Name</th>
            <th className="px-4 py-3">Type</th>
            <th className="px-4 py-3">Rows</th>
            <th className="px-4 py-3">Columns</th>
            <th className="px-4 py-3">Quality</th>
            <th className="px-4 py-3">Uploaded</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {datasets.map((dataset) => (
            <tr key={dataset.id} className="hover:bg-slate-50">
              <td className="px-4 py-3">
                <Link
                  to={`/datasets/${dataset.id}`}
                  className="font-medium text-accent-600 hover:text-accent-700 hover:underline"
                >
                  {dataset.name}
                </Link>
                <div className="text-xs text-slate-400">{dataset.original_filename}</div>
              </td>
              <td className="px-4 py-3 uppercase text-slate-500">{dataset.file_type}</td>
              <td className="px-4 py-3 text-slate-700">{dataset.row_count.toLocaleString()}</td>
              <td className="px-4 py-3 text-slate-700">{dataset.column_count}</td>
              <td className="px-4 py-3">
                <QualityScoreBadge score={dataset.quality_score} />
              </td>
              <td className="px-4 py-3 text-slate-500">{formatDate(dataset.created_at)}</td>
              <td className="px-4 py-3 text-right">
                {canDelete && (
                  <button
                    type="button"
                    onClick={() => onDelete(dataset)}
                    className="text-xs font-medium text-slate-400 hover:text-red-600"
                  >
                    Delete
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
