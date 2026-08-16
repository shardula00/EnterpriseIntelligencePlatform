import { useState } from 'react'
import type { DatasetSummary } from '../../api/types'
import { DatasetSelect } from '../analytics/DatasetSelect'

/** Two distinct actions, not one "Ask" button, matching the two distinct
 * backend endpoints: a what-if scenario is always stateless (never
 * persisted), a recommendation is always persisted with a pending
 * approval state - the UI should never blur that distinction for the
 * user either. */
export function DecisionQueryForm({
  datasets,
  datasetId,
  onDatasetChange,
  onRunScenario,
  onPropose,
  disabled,
}: {
  datasets: DatasetSummary[]
  datasetId: string | null
  onDatasetChange: (datasetId: string) => void
  onRunScenario: (question: string) => void
  onPropose: (question: string) => void
  disabled?: boolean
}) {
  const [question, setQuestion] = useState('')
  const canSubmit = !disabled && question.trim().length > 0 && !!datasetId

  return (
    <form
      onSubmit={(e) => e.preventDefault()}
      className="flex flex-col gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
      aria-label="Decision intelligence form"
    >
      <h2 className="text-sm font-semibold text-slate-900">
        🧭 Ask for a recommendation or run a what-if scenario
      </h2>

      <DatasetSelect datasets={datasets} value={datasetId} onChange={onDatasetChange} />

      <div>
        <label htmlFor="decision-question" className="mb-1 block text-xs font-medium text-slate-600">
          Question
        </label>
        <input
          id="decision-question"
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="What happens to profit if revenue decreases by 10%?"
          disabled={disabled}
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm placeholder:text-slate-400 focus:border-accent-500 focus:outline-none disabled:bg-slate-50"
        />
        {!datasetId && (
          <p className="mt-1 text-xs text-slate-400">Select a dataset above before asking.</p>
        )}
      </div>

      <div className="flex flex-col gap-2 sm:flex-row">
        <button
          type="button"
          onClick={() => canSubmit && onRunScenario(question.trim())}
          disabled={!canSubmit}
          className="rounded-md border border-accent-600 px-4 py-2 text-sm font-medium text-accent-600 hover:bg-accent-50 disabled:cursor-not-allowed disabled:border-slate-300 disabled:text-slate-400"
        >
          {disabled ? 'Working…' : 'Run What-If Scenario'}
        </button>
        <button
          type="button"
          onClick={() => canSubmit && onPropose(question.trim())}
          disabled={!canSubmit}
          className="rounded-md bg-accent-600 px-4 py-2 text-sm font-medium text-white hover:bg-accent-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {disabled ? 'Working…' : 'Propose Recommendation'}
        </button>
      </div>
    </form>
  )
}
