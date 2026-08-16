import { useState } from 'react'
import {
  ApiError,
  approveRecommendation,
  listDatasets,
  proposeRecommendation,
  rejectRecommendation,
  runScenario,
} from '../api/client'
import type { Recommendation, ScenarioResult } from '../api/types'
import { DecisionQueryForm } from '../components/decision/DecisionQueryForm'
import { ScenarioResultView } from '../components/decision/ScenarioResultView'
import { RecommendationView } from '../components/decision/RecommendationView'
import { LoadingSpinner } from '../components/common/LoadingSpinner'
import { ErrorMessage } from '../components/common/ErrorMessage'
import { EmptyState } from '../components/common/EmptyState'
import { useAsync } from '../hooks/useAsync'

export function DecisionsPage() {
  const datasetsResult = useAsync(() => listDatasets(), [])
  const [datasetId, setDatasetId] = useState<string | null>(null)

  const [status, setStatus] = useState<'idle' | 'working' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [scenarioResult, setScenarioResult] = useState<ScenarioResult | null>(null)
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null)

  function resetSelection(id: string) {
    setDatasetId(id)
    setScenarioResult(null)
    setRecommendation(null)
    setError(null)
  }

  async function handleRunScenario(question: string) {
    if (!datasetId) return
    setStatus('working')
    setError(null)
    setRecommendation(null)
    try {
      const result = await runScenario(datasetId, question)
      setScenarioResult(result)
      setStatus('idle')
    } catch (err) {
      setStatus('error')
      setError(
        err instanceof ApiError ? err.message : 'The scenario could not be computed. Please try again.',
      )
    }
  }

  async function handlePropose(question: string) {
    if (!datasetId) return
    setStatus('working')
    setError(null)
    setScenarioResult(null)
    try {
      const result = await proposeRecommendation(datasetId, question)
      setRecommendation(result)
      setStatus('idle')
    } catch (err) {
      setStatus('error')
      setError(
        err instanceof ApiError
          ? err.message
          : 'The recommendation could not be generated. Please try again.',
      )
    }
  }

  async function handleApprove() {
    if (!recommendation) return
    setStatus('working')
    setError(null)
    try {
      setRecommendation(await approveRecommendation(recommendation.id))
      setStatus('idle')
    } catch (err) {
      setStatus('error')
      setError(err instanceof ApiError ? err.message : 'Could not approve this recommendation.')
    }
  }

  async function handleReject() {
    if (!recommendation) return
    setStatus('working')
    setError(null)
    try {
      setRecommendation(await rejectRecommendation(recommendation.id))
      setStatus('idle')
    } catch (err) {
      setStatus('error')
      setError(err instanceof ApiError ? err.message : 'Could not reject this recommendation.')
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Decision Intelligence</h1>
        <p className="mt-1 text-sm text-slate-500">
          Run a verified what-if scenario, or generate an evidence-backed recommendation that a
          human must explicitly approve before it is treated as acted on.
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
            description="Upload a dataset from the Datasets page before requesting a decision."
          />
        ) : (
          <>
            <DecisionQueryForm
              datasets={datasetsResult.data}
              datasetId={datasetId}
              onDatasetChange={resetSelection}
              onRunScenario={handleRunScenario}
              onPropose={handlePropose}
              disabled={status === 'working'}
            />
            {status === 'error' && error && <ErrorMessage message={error} />}
            {scenarioResult && <ScenarioResultView result={scenarioResult} />}
            {recommendation && (
              <RecommendationView
                recommendation={recommendation}
                onApprove={handleApprove}
                onReject={handleReject}
                busy={status === 'working'}
              />
            )}
          </>
        ))}
    </div>
  )
}
