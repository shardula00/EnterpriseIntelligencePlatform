import { useCallback, useEffect, useRef, useState } from 'react'

type AsyncState<T> =
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: string }

/**
 * Minimal data-fetching hook covering the loading/success/error states
 * every screen needs. At this app's scale a small hook is enough - no
 * caching/invalidation library (e.g. React Query) is justified yet.
 */
export function useAsync<T>(fn: () => Promise<T>, deps: readonly unknown[]) {
  const [state, setState] = useState<AsyncState<T>>({ status: 'loading' })
  const fnRef = useRef(fn)
  fnRef.current = fn

  const load = useCallback(() => {
    setState({ status: 'loading' })
    fnRef.current().then(
      (data) => setState({ status: 'success', data }),
      (err: unknown) =>
        setState({ status: 'error', error: err instanceof Error ? err.message : String(err) }),
    )
    // deps is caller-controlled and intentionally drives when this re-runs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    load()
  }, [load])

  return { ...state, reload: load }
}
