import { useState } from 'react'
import type { ReactNode } from 'react'
import { predictMlRun } from '../../api/client'
import type { PredictionResponse } from '../../api/types'
import { usePermission } from '../../hooks/usePermission'
import { ErrorMessage } from '../common/ErrorMessage'

/** Triggers real (never mocked) predictions from an already-trained run
 * and renders whatever `children` wants from the response - shared by all
 * 4 result views so each only has to describe its own prediction table/
 * chart, not the fetch/loading/error plumbing. */
export function PredictAction({
  runId,
  horizon,
  buttonLabel = 'Run predictions',
  children,
}: {
  runId: string
  horizon?: number
  buttonLabel?: string
  children: (response: PredictionResponse) => ReactNode
}) {
  const canPredict = usePermission('ml:predict')
  const [status, setStatus] = useState<'idle' | 'loading' | 'error' | 'success'>('idle')
  const [response, setResponse] = useState<PredictionResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function run() {
    setStatus('loading')
    setError(null)
    try {
      const result = await predictMlRun(runId, horizon)
      setResponse(result)
      setStatus('success')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setStatus('error')
    }
  }

  if (!canPredict) {
    return (
      <p className="text-xs text-slate-400">
        Generating predictions requires Analyst or Admin access.
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <button
        type="button"
        onClick={run}
        disabled={status === 'loading'}
        className="self-start rounded-md border border-accent-300 bg-accent-50 px-4 py-2 text-sm font-medium text-accent-700 hover:bg-accent-100 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {status === 'loading' ? 'Predicting…' : buttonLabel}
      </button>
      {status === 'error' && error && <ErrorMessage message={error} onRetry={run} />}
      {status === 'success' && response && children(response)}
    </div>
  )
}
