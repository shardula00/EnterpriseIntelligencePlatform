import type { AnomalyResults } from '../../api/types'
import { isAnomalyPredictions } from '../../api/types'
import { MetricsRow } from './MetricsRow'
import { AnomalyScoreChart } from './AnomalyScoreChart'
import { PredictAction } from './PredictAction'

export function AnomalyResultsView({
  runId,
  results,
}: {
  runId: string
  results: AnomalyResults
}) {
  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-wrap gap-3">
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
          <p className="text-xs uppercase tracking-wide text-slate-400">Contamination (expected rate)</p>
          <p className="text-lg font-semibold text-slate-900">
            {Math.round(results.contamination * 100)}%
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
          <p className="text-xs uppercase tracking-wide text-slate-400">Flagged as anomalous</p>
          <p className="text-lg font-semibold text-slate-900">
            {results.anomaly_count.toLocaleString()} ({results.anomaly_percentage}%)
          </p>
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-900">Anomaly score distribution</h2>
        <MetricsRow metrics={results.score_summary} />
        <p className="mt-2 text-xs text-slate-500">
          Higher score = more anomalous (the Isolation Forest&apos;s decision function, negated for
          intuitive reading - see app/ml/anomaly_detection.py).
        </p>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-900">
          Most anomalous records ({Math.min(20, results.anomalous_records.length)} of{' '}
          {results.anomalous_records.length})
        </h2>
        <AnomalyScoreChart records={results.anomalous_records} />
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-900">Flagged record details</h2>
        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2">Row</th>
                <th className="px-3 py-2">Score</th>
                {results.feature_columns.map((column) => (
                  <th key={column} className="px-3 py-2">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {results.anomalous_records.slice(0, 20).map((record) => (
                <tr key={record.row_index}>
                  <td className="px-3 py-2 text-slate-500">{record.row_index}</td>
                  <td className="px-3 py-2 font-medium text-red-600">{record.anomaly_score}</td>
                  {results.feature_columns.map((column) => (
                    <td key={column} className="px-3 py-2 text-slate-600">
                      {String(record.values[column] ?? '')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-900">Score all rows</h2>
        <PredictAction runId={runId}>
          {(response) =>
            isAnomalyPredictions(response) ? (
              <p className="text-sm text-slate-600">
                Scored {response.summary.row_count as number} rows -{' '}
                {response.summary.anomaly_count as number} flagged as anomalous.
              </p>
            ) : null
          }
        </PredictAction>
      </section>
    </div>
  )
}
