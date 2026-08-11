import { useState } from 'react'
import { trainSegmentation } from '../../api/client'
import type { TaskSuitability } from '../../api/types'
import { FeatureColumnPicker } from './FeatureColumnPicker'
import { ErrorMessage } from '../common/ErrorMessage'

export function SegmentationConfigForm({
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
  const [nClusters, setNClusters] = useState(4)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const result = await trainSegmentation({ datasetId, featureColumns, nClusters })
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
        <span className="mb-1 block font-medium text-slate-700">Number of clusters ({nClusters})</span>
        <input
          type="range"
          min={2}
          max={8}
          step={1}
          value={nClusters}
          onChange={(e) => setNClusters(Number(e.target.value))}
          className="w-full"
        />
      </label>

      {error && <ErrorMessage message={error} />}

      <button
        type="submit"
        disabled={submitting || featureColumns.length < 2}
        className="self-start rounded-md bg-accent-600 px-4 py-2 text-sm font-medium text-white hover:bg-accent-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting ? 'Training…' : 'Train model'}
      </button>
    </form>
  )
}
