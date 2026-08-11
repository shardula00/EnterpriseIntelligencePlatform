import { useState } from 'react'
import { trainClassification } from '../../api/client'
import type { TaskSuitability } from '../../api/types'
import { FeatureColumnPicker } from './FeatureColumnPicker'
import { ErrorMessage } from '../common/ErrorMessage'

export function ClassificationConfigForm({
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
  const suggestedTargets = check.suggested_target_columns ?? []
  const [targetColumn, setTargetColumn] = useState(suggestedTargets[0] ?? '')
  const [featureColumns, setFeatureColumns] = useState<string[]>(check.suggested_feature_columns ?? [])
  const [testSize, setTestSize] = useState(0.25)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const result = await trainClassification({
        datasetId,
        targetColumn,
        featureColumns,
        testSize,
      })
      onTrained(result.run.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      <label className="text-sm">
        <span className="mb-1 block font-medium text-slate-700">Target column (binary)</span>
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

      <FeatureColumnPicker
        allColumns={columns}
        selected={featureColumns}
        onChange={setFeatureColumns}
        excluded={[targetColumn]}
      />

      <label className="text-sm">
        <span className="mb-1 block font-medium text-slate-700">
          Test split size ({Math.round(testSize * 100)}%)
        </span>
        <input
          type="range"
          min={0.1}
          max={0.5}
          step={0.05}
          value={testSize}
          onChange={(e) => setTestSize(Number(e.target.value))}
          className="w-full"
        />
      </label>

      {error && <ErrorMessage message={error} />}

      <button
        type="submit"
        disabled={submitting || !targetColumn || featureColumns.length === 0}
        className="self-start rounded-md bg-accent-600 px-4 py-2 text-sm font-medium text-white hover:bg-accent-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting ? 'Training…' : 'Train model'}
      </button>
    </form>
  )
}
