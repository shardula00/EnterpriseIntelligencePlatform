import { useState } from 'react'
import { Link } from 'react-router-dom'
import { registerModelVersion } from '../../api/client'
import { usePermission } from '../../hooks/usePermission'
import { ErrorMessage } from '../common/ErrorMessage'

/** Bridges Phase 5's run results page into the Phase 6 model registry -
 * "train a model" and "register a version" are deliberately separate
 * steps (see DEVELOPMENT_PLAN.md's Phase 6 acceptance flow), so this is an
 * explicit action a user takes here, not something that happens
 * automatically on every training run. */
export function RegisterVersionAction({ runId }: { runId: string }) {
  const canEvaluate = usePermission('mlops:evaluate')
  const [status, setStatus] = useState<'idle' | 'loading' | 'error' | 'success'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [versionId, setVersionId] = useState<string | null>(null)

  async function handleRegister() {
    setStatus('loading')
    setError(null)
    try {
      const version = await registerModelVersion(runId)
      setVersionId(version.id)
      setStatus('success')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setStatus('error')
    }
  }

  if (!canEvaluate) {
    return (
      <p className="text-xs text-slate-400">
        Registering a model version requires Analyst or Admin access.
      </p>
    )
  }

  if (status === 'success' && versionId) {
    return (
      <p className="text-sm text-emerald-700">
        Registered as a model version -{' '}
        <Link to={`/mlops/versions/${versionId}`} className="font-medium hover:underline">
          view it in the model registry
        </Link>
        .
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      <button
        type="button"
        onClick={handleRegister}
        disabled={status === 'loading'}
        className="self-start rounded-md border border-accent-300 bg-accent-50 px-4 py-2 text-sm font-medium text-accent-700 hover:bg-accent-100 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {status === 'loading' ? 'Registering…' : 'Register as model version'}
      </button>
      {status === 'error' && error && <ErrorMessage message={error} onRetry={handleRegister} />}
    </div>
  )
}
