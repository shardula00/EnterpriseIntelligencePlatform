import type { ColumnInfo } from '../../api/types'
import { EmptyState } from '../common/EmptyState'

const TYPE_LABELS: Record<string, string> = {
  integer: 'Integer',
  float: 'Float',
  boolean: 'Boolean',
  datetime: 'Datetime',
  text: 'Text',
}

export function SchemaTable({ columns }: { columns: ColumnInfo[] }) {
  if (columns.length === 0) {
    return <EmptyState title="No columns" />
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">Column</th>
            <th className="px-4 py-3">Type</th>
            <th className="px-4 py-3">Nulls</th>
            <th className="px-4 py-3">Distinct</th>
            <th className="px-4 py-3">Min</th>
            <th className="px-4 py-3">Max</th>
            <th className="px-4 py-3">Mean</th>
            <th className="px-4 py-3">Samples</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {columns.map((column) => (
            <tr key={column.column_name} className="hover:bg-slate-50">
              <td className="px-4 py-3">
                <div className="font-medium text-slate-800">{column.column_name}</div>
                {column.original_name !== column.column_name && (
                  <div className="text-xs text-slate-400">from “{column.original_name}”</div>
                )}
              </td>
              <td className="px-4 py-3">
                <span className="inline-flex rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                  {TYPE_LABELS[column.detected_type] ?? column.detected_type}
                </span>
              </td>
              <td className="px-4 py-3 text-slate-600">{column.null_count}</td>
              <td className="px-4 py-3 text-slate-600">{column.distinct_count}</td>
              <td className="px-4 py-3 text-slate-600">{column.min_value ?? '—'}</td>
              <td className="px-4 py-3 text-slate-600">{column.max_value ?? '—'}</td>
              <td className="px-4 py-3 text-slate-600">
                {column.mean_value != null ? column.mean_value.toFixed(2) : '—'}
              </td>
              <td className="max-w-xs truncate px-4 py-3 text-slate-500">
                {(column.sample_values ?? []).join(', ') || '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
