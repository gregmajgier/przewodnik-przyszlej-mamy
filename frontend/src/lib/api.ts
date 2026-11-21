export const TOKEN_KEY = 'token'

const BASE_URL: string = import.meta.env.VITE_API_URL ?? ''

/** Pełny adres endpointu (dla funkcji, które same czytają odpowiedź, np. strumień SSE czatu). */
export function apiUrl(path: string): string {
  return `${BASE_URL}${path}`
}

export class ApiError extends Error {
  readonly status: number
  readonly detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    // localStorage niedostępny — sesja będzie tylko w pamięci
  }
}

type ApiInit = Omit<RequestInit, 'body'> & { body?: unknown }

function extractDetail(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => (d as { msg?: unknown }).msg)
      .filter((m): m is string => typeof m === 'string')
      .map((m) => m.replace(/^Value error,\s*/, ''))
    if (msgs.length) return msgs.join('; ')
    return 'Niepoprawne dane. Sprawdź formularz.'
  }
  if (status === 401) return 'Sesja wygasła. Zaloguj się ponownie.'
  if (status >= 500) return 'Coś poszło nie tak po naszej stronie. Spróbuj ponownie za chwilę.'
  return 'Nie udało się wykonać operacji.'
}

/** Wywołanie API: dokleja Bearer, serializuje JSON, rzuca ApiError{status, detail}. */
export async function api<T>(path: string, init: ApiInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)

  let body: BodyInit | undefined
  if (init.body !== undefined) {
    if (typeof init.body === 'string' || init.body instanceof FormData) {
      body = init.body
    } else {
      body = JSON.stringify(init.body)
      if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
    }
  }

  let res: Response
  try {
    res = await fetch(`${BASE_URL}${path}`, { ...init, headers, body })
  } catch {
    throw new ApiError(0, 'Brak połączenia z serwerem. Sprawdź internet i spróbuj ponownie.')
  }

  if (res.status === 204) return undefined as T
  let data: unknown = null
  try {
    data = await res.json()
  } catch {
    data = null
  }
  if (!res.ok) throw new ApiError(res.status, extractDetail(data, res.status))
  return data as T
}
