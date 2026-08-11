import type { ClassificationResults } from '../../api/types'
import { isClassificationPredictions } from '../../api/types'
import { CandidateModelTable } from './CandidateModelTable'
import { MetricsRow } from './MetricsRow'
import { ConfusionMatrix } from './ConfusionMatrix'
import { FeatureImportanceChart } from './FeatureImportanceChart'
import { PredictAction } from './PredictAction'

export function ClassificationResultsView({
  runId,
  results,
}: {
  runId: string
  results: ClassificationResults
}) {
  return (
    <div className="flex flex-col gap-6">
      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-900">Model comparison</h2>
        <CandidateModelTable
          candidates={results.candidate_models}
          selectedModel={results.selected_model}
          primaryMetric={results.primary_metric}
        />
        <p className="mt-2 text-xs text-slate-500">{results.primary_metric_rationale}</p>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-900">
          {results.selected_model} - held-out test performance
        </h2>
        <MetricsRow metrics={results.metrics} />
      </section>

      <section className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <div>
          <h2 className="mb-2 text-sm font-semibold text-slate-900">Confusion matrix</h2>
          <ConfusionMatrix matrix={results.confusion_matrix} />
        </div>
        <div>
          <h2 className="mb-2 text-sm font-semibold text-slate-900">Class distribution</h2>
          <ul className="text-sm text-slate-600">
            {Object.entries(results.class_distribution).map(([label, count]) => (
              <li key={label}>
                <span className="font-medium text-slate-800">{label}</span>: {count.toLocaleString()}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-900">Feature importance</h2>
        <FeatureImportanceChart importance={results.feature_importance} />
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-900">
          Sample test-set predictions ({results.sample_predictions.length})
        </h2>
        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2">Row</th>
                <th className="px-3 py-2">Actual</th>
                <th className="px-3 py-2">Predicted</th>
                <th className="px-3 py-2">Probability</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {results.sample_predictions.map((p) => (
                <tr key={p.row_index} className={p.actual !== p.predicted ? 'bg-red-50' : ''}>
                  <td className="px-3 py-2 text-slate-500">{p.row_index}</td>
                  <td className="px-3 py-2 text-slate-700">{p.actual}</td>
                  <td className="px-3 py-2 text-slate-700">{p.predicted}</td>
                  <td className="px-3 py-2 text-slate-600">{p.probability}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-900">Predict on all rows</h2>
        <PredictAction runId={runId}>
          {(response) =>
            isClassificationPredictions(response) ? (
              <p className="text-sm text-slate-600">
                Scored {response.summary.row_count as number} rows -{' '}
                {response.summary.predicted_positive as number} predicted positive.
              </p>
            ) : null
          }
        </PredictAction>
      </section>
    </div>
  )
}
