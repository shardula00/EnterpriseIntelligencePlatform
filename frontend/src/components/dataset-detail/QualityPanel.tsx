import type { QualityIssue } from '../../api/types'
import { QualityScoreBadge } from '../datasets/QualityScoreBadge'
import { EmptyState } from '../common/EmptyState'

const SEVERITY_CLASSES: Record<string, string> = {
  critical: 'bg-red-50 text-red-700 ring-red-200',
  warning: 'bg-amber-50 text-amber-700 ring-amber-200',
  info: 'bg-slate-100 text-slate-600 ring-slate-200',
}

export function QualityPanel({ score, issues }: { score: number; issues: QualityIssue[] }) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <span className="text-3xl font-semibold text-slate-900">{score.toFixed(1)}</span>
        <QualityScoreBadge score={score} />
      </div>

      {issues.length === 0 ? (
        <EmptyState title="No quality issues found" description="Every validation rule passed." />
      ) : (
        <ul className="flex flex-col gap-2">
          {issues.map((issue, index) => (
            <li
              key={`${issue.rule}-${issue.column_name ?? 'dataset'}-${index}`}
              className="flex items-start justify-between gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
            >
              <div>
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${
                      SEVERITY_CLASSES[issue.severity] ?? SEVERITY_CLASSES.info
                    }`}
                  >
                    {issue.severity}
                  </span>
                  <span className="text-xs font-medium text-slate-400">{issue.rule}</span>
                  {issue.column_name && (
                    <span className="text-xs text-slate-400">· {issue.column_name}</span>
                  )}
                </div>
                <p className="mt-1 text-sm text-slate-700">{issue.message}</p>
              </div>
              <span className="whitespace-nowrap text-xs font-medium text-slate-400">
                -{issue.score_impact.toFixed(1)} pts
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
