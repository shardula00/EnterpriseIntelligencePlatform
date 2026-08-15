import { useState } from 'react'
import { ApiError, listDatasets, runAnalyticsQuery } from '../api/client'
import type { AnalyticsQueryResult } from '../api/types'
import { AnalyticsQueryForm } from '../components/analytics/AnalyticsQueryForm'
import { AnalyticsResultView } from '../components/analytics/AnalyticsResultView'
import { LoadingSpinner } from '../components/common/LoadingSpinner'
import { ErrorMessage } from '../components/common/ErrorMessage'
import { EmptyState } from '../components/common/EmptyState'
import { useAsync } from '../hooks/useAsync'

export function AnalyticsPage() {
  const datasetsResult = useAsync(() => listDatasets(), [])
  const [datasetId, setDatasetId] = useState<string | null>(null)

  const [status, setStatus] = useState<'idle' | 'asking' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<AnalyticsQueryResult | null>(null)

  async function handleAsk(question: string) {
    if (!datasetId) return
    setStatus('asking')
    setError(null)
    try {
      const response = await runAnalyticsQuery(datasetId, question)
      setResult(response)
      setStatus('idle')
    } catch (err) {
      setStatus('error')
      setError(
        err instanceof ApiError ? err.message : 'The question could not be answered. Please try again.',
      )
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Analytics</h1>
        <p className="mt-1 text-sm text-slate-500">
          Select a dataset and ask a plain-English analytical question - answered with the exact
          SQL query that was run.
        </p>
      </div>

      {datasetsResult.status === 'loading' && <LoadingSpinner label="Loading datasets…" />}
      {datasetsResult.status === 'error' && (
        <ErrorMessage message={datasetsResult.error} onRetry={datasetsResult.reload} />
      )}
      {datasetsResult.status === 'success' &&
        (datasetsResult.data.length === 0 ? (
          <EmptyState
            title="No datasets yet"
            description="Upload a dataset from the Datasets page before asking analytics questions."
          />
        ) : (
          <>
            <AnalyticsQueryForm
              datasets={datasetsResult.data}
              datasetId={datasetId}
              onDatasetChange={(id) => {
                setDatasetId(id)
                setResult(null)
                setError(null)
              }}
              onAsk={handleAsk}
              disabled={status === 'asking'}
            />
            {status === 'error' && error && <ErrorMessage message={error} />}
            {result && <AnalyticsResultView result={result} />}
          </>
        ))}
    </div>
  )
}
