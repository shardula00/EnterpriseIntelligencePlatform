import type { Preview } from '../../api/types'
import { EmptyState } from '../common/EmptyState'

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  return String(value)
}

export function PreviewTable({ preview }: { preview: Preview }) {
  if (preview.rows.length === 0) {
    return <EmptyState title="No rows to preview" />
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
          <tr>
            {preview.columns.map((column) => (
              <th key={column} className="whitespace-nowrap px-4 py-3">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {preview.rows.map((row, index) => (
            <tr key={index} className="hover:bg-slate-50">
              {preview.columns.map((column) => (
                <td key={column} className="whitespace-nowrap px-4 py-3 text-slate-700">
                  {formatCell(row[column])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
