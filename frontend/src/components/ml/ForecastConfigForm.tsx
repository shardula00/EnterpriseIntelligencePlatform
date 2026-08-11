import { useState } from 'react'
import { trainForecasting } from '../../api/client'
import type { TaskSuitability } from '../../api/types'
import { ErrorMessage } from '../common/ErrorMessage'

export function ForecastConfigForm({
  datasetId,
  check,
  onTrained,
}: {
  datasetId: string
  check: TaskSuitability
  onTrained: (runId: string) => void
}) {
  const suggestedDatetimes = check.suggested_datetime_columns ?? []
  const suggestedTargets = check.suggested_target_columns ?? []
  const [datetimeColumn, setDatetimeColumn] = useState(suggestedDatetimes[0] ?? '')
  const [targetColumn, setTargetColumn] = useState(suggestedTargets[0] ?? '')
  const [horizon, setHorizon] = useState(14)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const result = await trainForecasting({ datasetId, datetimeColumn, targetColumn, horizon })
      onTrained(result.run.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      <label className="text-sm">
        <span className="mb-1 block font-medium text-slate-700">Datetime column</span>
        <select
          value={datetimeColumn}
          onChange={(e) => setDatetimeColumn(e.target.value)}
          className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm text-slate-700 focus:border-accent-500 focus:outline-none"
        >
          {suggestedDatetimes.map((column) => (
            <option key={column} value={column}>
              {column}
            </option>
          ))}
        </select>
      </label>

      <label className="text-sm">
        <span className="mb-1 block font-medium text-slate-700">Target column (numeric)</span>
        <select
          value={targetColumn}
          onChange={(e) => setTargetColumn(e.target.value)}
          className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm text-slate-700 focus:border-accent-500 focus:outline-none"
        >
          {suggestedTargets.map((column) => (
            <option key={column} value={column}>
              {column}
            </option>
          ))}
        </select>
      </label>

      <label className="text-sm">
        <span className="mb-1 block font-medium text-slate-700">
          Forecast horizon ({horizon} periods)
        </span>
        <input
          type="range"
          min={1}
          max={90}
          step={1}
          value={horizon}
          onChange={(e) => setHorizon(Number(e.target.value))}
          className="w-full"
        />
      </label>

      {error && <ErrorMessage message={error} />}

      <button
        type="submit"
        disabled={submitting || !datetimeColumn || !targetColumn}
        className="self-start rounded-md bg-accent-600 px-4 py-2 text-sm font-medium text-white hover:bg-accent-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting ? 'Training…' : 'Train model'}
      </button>
    </form>
  )
}
