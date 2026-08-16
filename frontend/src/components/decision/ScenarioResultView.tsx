import type { ScenarioResult } from '../../api/types'

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return value.toLocaleString('en-US', { maximumFractionDigits: 2 })
}

/** Always visibly distinguishes "computed" from "not computed" - a
 * declined scenario (no verified relationship in the actual data) is
 * rendered as an honest explanation, never a table with fabricated
 * numbers. See app/decision/scenario.py. */
export function ScenarioResultView({ result }: { result: ScenarioResult }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-900">What-If Scenario</h3>
        <span
          className={`rounded-full px-2.5 py-1 text-xs font-medium ${
            result.computed ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'
          }`}
        >
          {result.computed ? 'Computed' : 'Not computed'}
        </span>
      </div>

      {!result.computed && <p className="mt-3 text-sm text-slate-600">{result.reason}</p>}

      {result.computed && (
        <>
          <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-xs text-slate-500">Change</dt>
              <dd className="font-medium text-slate-800">
                {result.perturbed_metric}{' '}
                {result.delta_percent !== null && result.delta_percent !== undefined
                  ? `${result.delta_percent > 0 ? '+' : ''}${result.delta_percent}%`
                  : ''}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Baseline {result.perturbed_metric}</dt>
              <dd className="font-medium text-slate-800">{formatNumber(result.baseline_perturbed_value)}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">New {result.perturbed_metric}</dt>
              <dd className="font-medium text-slate-800">{formatNumber(result.new_perturbed_value)}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Baseline {result.affected_metric}</dt>
              <dd className="font-medium text-slate-800">{formatNumber(result.baseline_affected_value)}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">New {result.affected_metric}</dt>
              <dd className="font-medium text-slate-800">{formatNumber(result.new_affected_value)}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Change in {result.affected_metric}</dt>
              <dd className="font-medium text-slate-800">{formatNumber(result.affected_value_change)}</dd>
            </div>
          </dl>
          <p className="mt-4 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">{result.note}</p>
        </>
      )}
    </div>
  )
}
