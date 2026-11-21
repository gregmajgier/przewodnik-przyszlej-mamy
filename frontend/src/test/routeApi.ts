import { vi } from 'vitest'
import { api, ApiError } from '../lib/api'

type Handler = unknown | ((init?: { body?: unknown; method?: string }) => unknown)

/**
 * Konfiguruje zamockowane `api` (wymaga `vi.mock('../../lib/api', ...)` w pliku testu).
 * Klucz: "METHOD /ścieżka", np. "GET /api/families/me". Wartość: dane, ApiError lub funkcja.
 */
export function routeApi(routes: Record<string, Handler>) {
  const mocked = vi.mocked(api)
  mocked.mockReset()
  mocked.mockImplementation((async (path: string, init?: { method?: string; body?: unknown }) => {
    const key = `${init?.method ?? 'GET'} ${path}`
    if (!(key in routes)) throw new ApiError(404, `Brak atrapy dla ${key}`)
    const h = routes[key]
    const value = typeof h === 'function' ? (h as (i?: unknown) => unknown)(init) : h
    if (value instanceof Error) throw value
    return value
  }) as unknown as typeof api)
  return mocked
}
