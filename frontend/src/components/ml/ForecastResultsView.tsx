import { useState } from 'react'
import type { ForecastResults } from '../../api/types'
import { isForecastPredictions } from '../../api/types'
import { CandidateModelTable } from './CandidateModelTable'
import { MetricsRow } from './MetricsRow'
import { ForecastChart } from './ForecastChart'
import { PredictAction } from './PredictAction'

export function ForecastResultsView({
  runId,
  results,
}: {
  runId: string
  results: ForecastResults
}) {
  const [horizon, setHorizon] = useState(results.horizon)

  return (
    <div className="flex flex-col gap-6">
      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-900">
          Historical values &amp; {results.horizon}-period forecast
        </h2>
        <ForecastChart historical={results.historical} forecast={results.forecast} />
        {!results.has_confidence_interval && (
          <p className="mt-2 text-xs text-slate-400">
            No confidence interval is shown - the selected model ({results.selected_model}) doesn&apos;t
            produce one (only Random Forest does, from the spread across its individual trees).
          </p>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-900">Baseline &amp; model comparison</h2>
        <p className="mb-2 text-xs text-slate-500">
          Naive/Seasonal Naive are baselines, not trained models - every candidate is backtested on
          the same held-out {results.horizon} real periods at the end of the series.
        </p>
        <CandidateModelTable
          candidates={results.candidate_models}
          selectedModel={results.selected_model}
          primaryMetric={results.primary_metric}
          lowerIsBetter
        />
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-900">
          {results.selected_model} - backtest error
        </h2>
        <MetricsRow metrics={results.metrics} />
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-900">Extend the forecast</h2>
        <label className="mb-3 block text-sm text-slate-600">
          Periods to forecast ({horizon})
          <input
            type="range"
            min={1}
            max={90}
            value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value))}
            className="mt-1 block w-full max-w-xs"
          />
        </label>
        <PredictAction runId={runId} horizon={horizon} buttonLabel={`Forecast next ${horizon} periods`}>
          {(response) =>
            isForecastPredictions(response) ? (
              <ForecastChart historical={results.historical} forecast={response.predictions} />
            ) : null
          }
        </PredictAction>
      </section>
    </div>
  )
}
