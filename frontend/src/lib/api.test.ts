import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, apiBlob, ApiError, TOKEN_KEY } from './api'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

async function fail(p: Promise<unknown>): Promise<ApiError> {
  try {
    await p
  } catch (e) {
    return e as ApiError
  }
  throw new Error('oczekiwano błędu')
}

describe('api', () => {
  afterEach(() => vi.restoreAllMocks())

  it('dokleja Bearer z localStorage("token")', async () => {
    localStorage.setItem(TOKEN_KEY, 'abc.def')
    const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ ok: 1 }))
    const data = await api<{ ok: number }>('/api/me')
    expect(data).toEqual({ ok: 1 })
    const [url, init] = spy.mock.calls[0]
    expect(String(url)).toMatch(/\/api\/me$/)
    expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer abc.def')
  })

  it('bez tokenu nie wysyła Authorization', async () => {
    const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({}))
    await api('/api/auth/personas')
    expect(new Headers(spy.mock.calls[0][1]?.headers).has('Authorization')).toBe(false)
  })

  it('serializuje body obiektowe jako JSON', async () => {
    const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({}))
    await api('/api/families', { method: 'POST', body: { name: 'X' } })
    const init = spy.mock.calls[0][1]!
    expect(init.body).toBe('{"name":"X"}')
    expect(new Headers(init.headers).get('Content-Type')).toBe('application/json')
  })

  it('mapuje 401 na ApiError ze statusem i polskim detail', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ detail: 'Sesja wygasła' }, 401))
    const err = await fail(api('/api/me'))
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(401)
    expect(err.detail).toBe('Sesja wygasła')
  })

  it('błąd walidacji 422 (lista) daje czytelny komunikat', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      jsonResponse({ detail: [{ msg: 'Value error, Podaj datę' }] }, 422),
    )
    const err = await fail(api('/x', { method: 'POST', body: {} }))
    expect(err.status).toBe(422)
    expect(typeof err.detail).toBe('string')
    expect(err.detail.length).toBeGreaterThan(0)
  })

  it('204 zwraca undefined', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 204 }))
    expect(await api('/x', { method: 'DELETE' })).toBeUndefined()
  })

  it('błąd sieci zamienia na ApiError ze statusem 0', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    const err = await fail(api('/x'))
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(0)
  })
})

describe('apiBlob', () => {
  afterEach(() => vi.restoreAllMocks())

  it('pobiera plik z nagłówkiem Bearer', async () => {
    localStorage.setItem(TOKEN_KEY, 'abc.def')
    const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('%PDF-1.4', { status: 200, headers: { 'Content-Type': 'application/pdf' } }),
    )
    const blob = await apiBlob('/api/applications/app-1/pdf')
    expect(await blob.text()).toBe('%PDF-1.4')
    const [url, init] = spy.mock.calls[0]
    expect(String(url)).toMatch(/\/api\/applications\/app-1\/pdf$/)
    expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer abc.def')
  })

  it('błąd HTTP z JSON-em zamienia na ApiError z polskim detail', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ detail: 'Uzupełnij brakujące dane, żeby zobaczyć podgląd.' }, 409))
    const err = await fail(apiBlob('/api/applications/app-1/pdf'))
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(409)
    expect(err.detail).toBe('Uzupełnij brakujące dane, żeby zobaczyć podgląd.')
  })

  it('błąd bez JSON-a daje komunikat domyślny, a błąd sieci status 0', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(new Response('boom', { status: 500 }))
    expect((await fail(apiBlob('/x'))).detail).toMatch(/po naszej stronie/)
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new TypeError('Failed to fetch'))
    expect((await fail(apiBlob('/x'))).status).toBe(0)
  })
})
