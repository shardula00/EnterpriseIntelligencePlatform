import { useState } from 'react'
import type { DatasetSummary } from '../../api/types'
import { DatasetSelect } from './DatasetSelect'

export function AnalyticsQueryForm({
  datasets,
  datasetId,
  onDatasetChange,
  onAsk,
  disabled,
}: {
  datasets: DatasetSummary[]
  datasetId: string | null
  onDatasetChange: (datasetId: string) => void
  onAsk: (question: string) => void
  disabled?: boolean
}) {
  const [question, setQuestion] = useState('')

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = question.trim()
    if (!trimmed || !datasetId) return
    onAsk(trimmed)
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
      aria-label="Analytics query form"
    >
      <h2 className="text-sm font-semibold text-slate-900">📊 Ask a question about your data</h2>

      <DatasetSelect datasets={datasets} value={datasetId} onChange={onDatasetChange} />

      <div>
        <label htmlFor="analytics-question" className="mb-1 block text-xs font-medium text-slate-600">
          Question
        </label>
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            id="analytics-question"
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="What is the total revenue?"
            disabled={disabled}
            className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm placeholder:text-slate-400 focus:border-accent-500 focus:outline-none disabled:bg-slate-50"
          />
          <button
            type="submit"
            disabled={disabled || !question.trim() || !datasetId}
            className="rounded-md bg-accent-600 px-5 py-2 text-sm font-medium text-white hover:bg-accent-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {disabled ? 'Asking…' : 'Ask'}
          </button>
        </div>
        {!datasetId && (
          <p className="mt-1 text-xs text-slate-400">Select a dataset above before asking.</p>
        )}
      </div>
    </form>
  )
}
