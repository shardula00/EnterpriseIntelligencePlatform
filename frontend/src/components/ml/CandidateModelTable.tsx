import type { CandidateModelMetrics } from '../../api/types'

/** Shared by classification and forecasting - both report a list of
 * candidate models each scored on the same set of metrics, with one
 * chosen as the winner. Renders every metric each candidate reports
 * (they're the same set for every candidate within one run). */
export function CandidateModelTable({
  candidates,
  selectedModel,
  primaryMetric,
  lowerIsBetter = false,
}: {
  candidates: CandidateModelMetrics[]
  selectedModel: string
  primaryMetric: string
  /** Forecasting's primary metric (MAE) is an error - lower wins.
   * Classification's (ROC-AUC) is a score - higher wins. Only affects
   * which direction "winner" highlighting explains, not the selection
   * itself (the backend already picked selectedModel). */
  lowerIsBetter?: boolean
}) {
  const metricNames = Object.keys(candidates[0]?.metrics ?? {})

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-3 py-2">Model</th>
            {metricNames.map((name) => (
              <th key={name} className={`px-3 py-2 ${name === primaryMetric ? 'text-accent-700' : ''}`}>
                {name}
                {name === primaryMetric ? ` (${lowerIsBetter ? 'lower' : 'higher'} is better)` : ''}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {candidates.map((candidate) => (
            <tr
              key={candidate.model_name}
              className={candidate.model_name === selectedModel ? 'bg-accent-50' : ''}
            >
              <td className="px-3 py-2 font-medium text-slate-800">
                {candidate.model_name}
                {candidate.model_name === selectedModel && (
                  <span className="ml-2 rounded-full bg-accent-100 px-2 py-0.5 text-xs font-medium text-accent-700">
                    Selected
                  </span>
                )}
              </td>
              {metricNames.map((name) => (
                <td key={name} className="px-3 py-2 text-slate-600">
                  {candidate.metrics[name]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
