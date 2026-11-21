import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '../../lib/api'
import type { CalendarEvent } from './types'

export function useCalendar(query = '') {
  const [events, setEvents] = useState<CalendarEvent[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api<CalendarEvent[]>(`/api/calendar${query}`)
      .then((r) => !cancelled && setEvents(r))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.detail : 'Nie udało się pobrać kalendarza.'))
    return () => {
      cancelled = true
    }
  }, [query])

  const toggle = useCallback(async (ev: CalendarEvent, done: boolean) => {
    setBusyId(ev.id)
    setError(null)
    try {
      const updated = await api<CalendarEvent>(`/api/calendar/${ev.id}`, { method: 'PATCH', body: { done } })
      setEvents((prev) => prev?.map((e) => (e.id === ev.id ? updated : e)) ?? prev)
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Nie udało się zapisać zmiany.')
    } finally {
      setBusyId(null)
    }
  }, [])

  return { events, error, busyId, toggle }
}
