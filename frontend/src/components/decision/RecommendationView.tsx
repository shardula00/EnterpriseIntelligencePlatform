import type { Recommendation } from '../../api/types'
import { usePermission } from '../../hooks/usePermission'

const CONFIDENCE_STYLES: Record<string, string> = {
  low: 'bg-red-100 text-red-700',
  medium: 'bg-amber-100 text-amber-700',
  high: 'bg-emerald-100 text-emerald-700',
}

const STATUS_STYLES: Record<string, string> = {
  pending: 'bg-slate-100 text-slate-600',
  approved: 'bg-emerald-100 text-emerald-700',
  rejected: 'bg-red-100 text-red-700',
}

/** Shows every field a Recommendation carries, kept visibly separated so
 * a recommendation is never mistaken for a certain fact: the suggestion
 * text, its alternatives, the real evidence it's based on (tagged by
 * originating agent), Risk's own risk flags (never re-represented),
 * explicit assumptions, a coarse confidence label, and - critically -
 * its approval status. Approve/Reject only render for a user who actually
 * has decision:approve; the backend independently re-enforces that same
 * permission regardless (see app/api/decisions.py). */
export function RecommendationView({
  recommendation,
  onApprove,
  onReject,
  busy,
}: {
  recommendation: Recommendation
  onApprove: () => void
  onReject: () => void
  busy?: boolean
}) {
  const canApprove = usePermission('decision:approve')

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-900">Recommendation</h3>
        <div className="flex items-center gap-2">
          <span
            className={`rounded-full px-2.5 py-1 text-xs font-medium ${CONFIDENCE_STYLES[recommendation.confidence]}`}
          >
            Confidence: {recommendation.confidence}
          </span>
          <span
            className={`rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_STYLES[recommendation.status]}`}
          >
            {recommendation.status}
          </span>
        </div>
      </div>

      <p className="mt-3 text-sm text-slate-700">{recommendation.recommendation}</p>

      {recommendation.alternatives.length > 0 && (
        <div className="mt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Alternatives</h4>
          <ul className="mt-1 list-inside list-disc text-sm text-slate-600">
            {recommendation.alternatives.map((alternative) => (
              <li key={alternative}>{alternative}</li>
            ))}
          </ul>
        </div>
      )}

      {recommendation.evidence.length > 0 && (
        <div className="mt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Evidence</h4>
          <ul className="mt-1 flex flex-col gap-1 text-sm text-slate-600">
            {recommendation.evidence.map((item, index) => (
              // eslint-disable-next-line react/no-array-index-key -- evidence items have no stable id
              <li key={index} className="rounded-md bg-slate-50 px-3 py-2">
                <span className="font-medium text-slate-700">{String(item.agent)}:</span>{' '}
                {String(item.summary)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {recommendation.risks.length > 0 && (
        <div className="mt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Risks</h4>
          <ul className="mt-1 flex flex-col gap-1 text-sm">
            {recommendation.risks.map((risk, index) => (
              // eslint-disable-next-line react/no-array-index-key -- risk flags have no stable id
              <li key={index} className="rounded-md bg-red-50 px-3 py-2 text-red-800">
                [{String(risk.severity)}] {String(risk.message)}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-4">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Expected Impact</h4>
        {recommendation.expected_impact ? (
          <p className="mt-1 text-sm text-slate-600">
            {String(recommendation.expected_impact.affected_metric)} changes by{' '}
            {String(recommendation.expected_impact.affected_value_change)} (
            {String(recommendation.expected_impact.relationship)})
          </p>
        ) : (
          <p className="mt-1 text-xs text-slate-400">
            Not quantified - no verified what-if scenario was part of this request.
          </p>
        )}
      </div>

      {recommendation.assumptions.length > 0 && (
        <div className="mt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Assumptions</h4>
          <ul className="mt-1 list-inside list-disc text-xs text-slate-500">
            {recommendation.assumptions.map((assumption) => (
              <li key={assumption}>{assumption}</li>
            ))}
          </ul>
        </div>
      )}

      {canApprove && recommendation.status === 'pending' && (
        <div className="mt-5 flex gap-2 border-t border-slate-100 pt-4">
          <button
            type="button"
            onClick={onApprove}
            disabled={busy}
            className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            Approve
          </button>
          <button
            type="button"
            onClick={onReject}
            disabled={busy}
            className="rounded-md border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:border-slate-300 disabled:text-slate-400"
          >
            Reject
          </button>
        </div>
      )}
    </div>
  )
}
