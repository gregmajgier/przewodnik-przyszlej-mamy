import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { TOKEN_KEY } from './api'
import { SessionProvider, useSession } from './session'

const USER = {
  id: 'user-nowak-anna',
  role: 'parent',
  name: 'Anna Nowak',
  email: null,
  persona_id: 'persona-nowak-anna',
  family_id: null,
  unit_id: null,
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status })
}

function mockApi(routes: Record<string, () => Response>) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const path = String(input).replace(/^https?:\/\/[^/]+/, '')
    const handler = routes[path]
    if (!handler) return json({ detail: `brak ${path}` }, 404)
    return handler()
  })
}

function Probe() {
  const { user, family, token, loading, login, logout } = useSession()
  return (
    <div>
      <span data-testid="state">
        {loading ? 'loading' : user ? `user:${user.name}` : 'anon'}|{family ? 'family' : 'nofamily'}|
        {token ?? 'notoken'}
      </span>
      <button onClick={() => login('persona-nowak-anna')}>login</button>
      <button onClick={() => logout()}>logout</button>
    </div>
  )
}

function setup() {
  return render(
    <SessionProvider>
      <Probe />
    </SessionProvider>,
  )
}

describe('SessionProvider', () => {
  afterEach(() => vi.restoreAllMocks())

  it('bez tokenu: anon, bez wywołań API', async () => {
    const spy = mockApi({})
    setup()
    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('anon|nofamily|notoken'))
    expect(spy).not.toHaveBeenCalled()
  })

  it('na publicznej ścieżce /jaskolka nie odtwarza sesji (żadnego żądania z tokenem)', async () => {
    localStorage.setItem(TOKEN_KEY, 'tok')
    const spy = mockApi({ '/api/me': () => json(USER) })
    window.history.pushState({}, '', '/jaskolka/poronienie')
    try {
      setup()
      await waitFor(() => expect(screen.getByTestId('state').textContent).not.toContain('loading'))
      expect(spy).not.toHaveBeenCalled()
    } finally {
      window.history.pushState({}, '', '/')
    }
  })

  it('login zapisuje token, ustawia usera; brak rodziny (404) => family null', async () => {
    mockApi({
      '/api/auth/mobywatel': () => json({ token: 'tok', user: USER }),
      '/api/families/me': () => json({ detail: 'Nie należysz jeszcze do żadnej rodziny.' }, 404),
    })
    setup()
    await userEvent.click(screen.getByText('login'))
    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe('user:Anna Nowak|nofamily|tok'),
    )
    expect(localStorage.getItem(TOKEN_KEY)).toBe('tok')
  })

  it('login pobiera rodzinę, gdy istnieje', async () => {
    mockApi({
      '/api/auth/mobywatel': () => json({ token: 'tok', user: { ...USER, family_id: 'f1' } }),
      '/api/families/me': () =>
        json({ family: { id: 'f1' }, members: [], children: [], pending_requests: [] }),
    })
    setup()
    await userEvent.click(screen.getByText('login'))
    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe('user:Anna Nowak|family|tok'),
    )
  })

  it('logout czyści token i stan', async () => {
    mockApi({
      '/api/auth/mobywatel': () => json({ token: 'tok', user: USER }),
      '/api/families/me': () => json({ detail: 'x' }, 404),
    })
    setup()
    await userEvent.click(screen.getByText('login'))
    await waitFor(() => expect(screen.getByTestId('state').textContent).toContain('user:'))
    await userEvent.click(screen.getByText('logout'))
    expect(screen.getByTestId('state').textContent).toBe('anon|nofamily|notoken')
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
  })

  it('istniejący token: odtwarza sesję z /api/me', async () => {
    localStorage.setItem(TOKEN_KEY, 'stary')
    mockApi({
      '/api/me': () => json(USER),
      '/api/families/me': () => json({ detail: 'x' }, 404),
    })
    setup()
    expect(screen.getByTestId('state').textContent).toContain('loading')
    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe('user:Anna Nowak|nofamily|stary'),
    )
  })

  it('nieważny token (401): czyści sesję', async () => {
    localStorage.setItem(TOKEN_KEY, 'zly')
    mockApi({ '/api/me': () => json({ detail: 'Sesja wygasła' }, 401) })
    setup()
    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('anon|nofamily|notoken'))
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
  })

  it('useSession poza providerem rzuca czytelny błąd', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<Probe />)).toThrow(/SessionProvider/)
    spy.mockRestore()
    act(() => {})
  })
})
