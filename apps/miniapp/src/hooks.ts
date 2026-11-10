import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from './api'

export interface AsyncState<T> {
  data: T | undefined
  error: ApiError | undefined
  loading: boolean
  reload(): void
}

/** Runs `fn` on mount and whenever `deps` change; with `pollMs` it refetches quietly while the page is visible. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[], pollMs?: number): AsyncState<T> {
  const [data, setData] = useState<T>()
  const [error, setError] = useState<ApiError>()
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  const fnRef = useRef(fn)
  fnRef.current = fn

  useEffect(() => {
    let alive = true
    setLoading(true)
    fnRef
      .current()
      .then((d) => {
        if (alive) {
          setData(d)
          setError(undefined)
        }
      })
      .catch((e: unknown) => {
        if (alive) setError(e instanceof ApiError ? e : new ApiError('generic', 0))
      })
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  useEffect(() => {
    if (!pollMs) return
    const id = setInterval(() => {
      if (document.visibilityState === 'hidden') return
      fnRef
        .current()
        .then((d) => {
          setData(d)
          setError(undefined)
        })
        .catch(() => undefined) // a failed refresh keeps the last good data on screen
    }, pollMs)
    return () => clearInterval(id)
  }, [pollMs, ...deps])

  const reload = useCallback(() => setTick((n) => n + 1), [])
  return { data, error, loading, reload }
}

/** Runs an action with a busy flag and an error message; returns the action's result or undefined on failure. */
export function useAction() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError>()
  const run = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setBusy(true)
    setError(undefined)
    try {
      return await fn()
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError('generic', 0))
      return undefined
    } finally {
      setBusy(false)
    }
  }, [])
  return { busy, error, run, clear: () => setError(undefined) }
}

export function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setV(value), ms)
    return () => clearTimeout(id)
  }, [value, ms])
  return v
}
