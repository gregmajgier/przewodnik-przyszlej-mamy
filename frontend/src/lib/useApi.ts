import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from './api'

/** Pobranie danych z API przy montowaniu (i po zmianie ścieżki). `path = null` — nic nie pobieramy. */
export function useApi<T>(path: string | null, fallbackError = 'Nie udało się wczytać danych.') {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (path === null) return
    let cancelled = false
    api<T>(path)
      .then((d) => {
        if (cancelled) return
        setData(d)
        setError(null)
      })
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.detail : fallbackError))
    return () => {
      cancelled = true
    }
  }, [path, tick, fallbackError])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { data, error, loading: path !== null && data === null && error === null, reload, setData }
}
