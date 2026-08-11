import { useState } from 'react'
import { trainAnomalyDetection } from '../../api/client'
import type { TaskSuitability } from '../../api/types'
import { FeatureColumnPicker } from './FeatureColumnPicker'
import { ErrorMessage } from '../common/ErrorMessage'

export function AnomalyConfigForm({
  datasetId,
  columns,
  check,
  onTrained,
}: {
  datasetId: string
  columns: string[]
  check: TaskSuitability
  onTrained: (runId: string) => void
}) {
  const [featureColumns, setFeatureColumns] = useState<string[]>(check.suggested_feature_columns ?? [])
  const [contamination, setContamination] = useState(0.05)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const result = await trainAnomalyDetection({ datasetId, featureColumns, contamination })
      onTrained(result.run.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      <FeatureColumnPicker allColumns={columns} selected={featureColumns} onChange={setFeatureColumns} />

      <label className="text-sm">
        <span className="mb-1 block font-medium text-slate-700">
          Expected anomaly rate ({Math.round(contamination * 100)}%)
        </span>
        <input
          type="range"
          min={0.01}
          max={0.3}
          step={0.01}
          value={contamination}
          onChange={(e) => setContamination(Number(e.target.value))}
          className="w-full"
        />
      </label>

      {error && <ErrorMessage message={error} />}

      <button
        type="submit"
        disabled={submitting || featureColumns.length === 0}
        className="self-start rounded-md bg-accent-600 px-4 py-2 text-sm font-medium text-white hover:bg-accent-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting ? 'Training…' : 'Train model'}
      </button>
    </form>
  )
}
