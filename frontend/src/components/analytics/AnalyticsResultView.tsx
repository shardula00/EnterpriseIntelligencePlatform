import type { AnalyticsQueryResult, AnalyticsQueryStatus } from '../../api/types'
import { EmptyState } from '../common/EmptyState'

const STATUS_LABELS: Record<AnalyticsQueryStatus, string> = {
  answered: 'Answered',
  unsupported: 'Unsupported question',
  error: 'Error',
}

const STATUS_STYLES: Record<AnalyticsQueryStatus, string> = {
  answered: 'bg-emerald-100 text-emerald-700',
  unsupported: 'bg-slate-100 text-slate-600',
  error: 'bg-red-100 text-red-700',
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return '—'
  // Explicit locale: toLocaleString() with no argument follows the
  // runtime's default locale, which is not necessarily en-US (and
  // produces a different digit grouping, e.g. "12,40,000" under en-IN) -
  // pinned so number formatting is consistent regardless of where this
  // runs.
  if (typeof value === 'number') return value.toLocaleString('en-US')
  return String(value)
}

/** Renders one answered question: the generated SQL (always shown for
 * transparency - see DEVELOPMENT_PLAN.md's Phase 8 "AI-generated
 * explanation" requirement), then the result as a plain table. For
 * "unsupported"/"error" statuses, shows the explanation instead - never a
 * table with no data and no reason why. */
export function AnalyticsResultView({ result }: { result: AnalyticsQueryResult }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-900">“{result.question}”</h3>
        <span
          className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_STYLES[result.status]}`}
        >
          {STATUS_LABELS[result.status]}
        </span>
      </div>

      {result.status !== 'answered' && (
        <p className="mt-3 text-sm text-slate-600">
          {result.error_message ??
            'This question could not be answered. Try rephrasing it, e.g. "total <column>", ' +
              '"<column> by <category>", or "which <category> has the highest <column>".'}
        </p>
      )}

      {result.status === 'answered' && result.generated_sql && (
        <div className="mt-3">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Generated SQL
          </h4>
          <pre className="mt-1 overflow-x-auto rounded-md bg-slate-900 px-3 py-2 text-xs text-slate-100">
            <code>{result.generated_sql}</code>
          </pre>
        </div>
      )}

      {result.status === 'answered' &&
        (result.rows.length === 0 ? (
          <div className="mt-3">
            <EmptyState
              title="No matching rows"
              description="The query ran successfully but returned no data."
            />
          </div>
        ) : (
          <div className="mt-3 overflow-x-auto rounded-lg border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                <tr>
                  {result.columns.map((column) => (
                    <th key={column} className="px-4 py-2">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {result.rows.map((row, i) => (
                  // eslint-disable-next-line react/no-array-index-key -- rows have no stable id
                  <tr key={i} className="hover:bg-slate-50">
                    {result.columns.map((column) => (
                      <td key={column} className="px-4 py-2 text-slate-700">
                        {formatCell(row[column])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
    </div>
  )
}
