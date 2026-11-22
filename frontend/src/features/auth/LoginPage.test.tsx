import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { markOnboarded } from '../../lib/onboarding'
import { SessionContext } from '../../lib/session'
import type { SessionValue } from '../../lib/session'
import { ANNA, makeSession, renderWithSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import LoginPage from './LoginPage'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

const PERSONAS = [
  { id: 'persona-nowak-anna', name: 'Anna Nowak', role_label: 'Mama, 31 lat, Kraków' },
  { id: 'persona-nowak-piotr', name: 'Piotr Nowak', role_label: 'Tata, 34 lata, Kraków' },
]

function Tree() {
  return (
    <Routes>
      <Route path="/logowanie" element={<LoginPage />} />
      <Route path="/start" element={<p>Strona start</p>} />
      <Route path="/" element={<p>Strona główna</p>} />
      <Route path="/poczta" element={<p>Poczta</p>} />
    </Routes>
  )
}

/** Ekran powitania → „Zaloguj przez mObywatel” → lista profili. */
async function openAccounts() {
  await userEvent.click(screen.getByRole('button', { name: /zaczynamy/i }))
  await userEvent.click(screen.getByRole('button', { name: /zaloguj przez mobywatel/i }))
}

function renderWithReturnPath(session: SessionValue, from: unknown) {
  return render(
    <SessionContext.Provider value={session}>
      <MemoryRouter initialEntries={[{ pathname: '/logowanie', state: { from } }]}>
        <Tree />
      </MemoryRouter>
    </SessionContext.Provider>,
  )
}

describe('LoginPage', () => {
  beforeEach(() => {
    routeApi({ 'GET /api/auth/personas': PERSONAS })
  })

  it('pokazuje persony i po kliknięciu loguje oraz przekierowuje na /start (brak rodziny)', async () => {
    const session = makeSession({ user: null, token: null })
    renderWithSession(<Tree />, { route: '/logowanie', session })
    expect(screen.getByText(/mamo! tato!/i)).toBeInTheDocument()
    await openAccounts()
    const anna = await screen.findByRole('button', { name: /Anna Nowak/ })
    expect(screen.getByRole('button', { name: /Piotr Nowak/ })).toBeInTheDocument()
    await userEvent.click(anna)
    expect(session.login).toHaveBeenCalledWith('persona-nowak-anna')
    expect(await screen.findByText('Strona start')).toBeInTheDocument()
  })

  it('użytkownik z rodziną, który przeszedł już onboarding na tym urządzeniu, trafia na /', async () => {
    markOnboarded(ANNA.id)
    const session = makeSession({
      user: null,
      token: null,
      login: vi.fn(async () => ({
        user: ANNA,
        family: { family: {}, members: [], children: [], pending_requests: [] } as never,
      })),
    })
    renderWithSession(<Tree />, { route: '/logowanie', session })
    await openAccounts()
    await userEvent.click(await screen.findByRole('button', { name: /Anna Nowak/ }))
    expect(await screen.findByText('Strona główna')).toBeInTheDocument()
  })

  it('użytkownik z rodziną, ale na nowym urządzeniu, przechodzi onboarding od początku', async () => {
    const session = makeSession({
      user: null,
      token: null,
      login: vi.fn(async () => ({
        user: ANNA,
        family: { family: {}, members: [], children: [], pending_requests: [] } as never,
      })),
    })
    renderWithSession(<Tree />, { route: '/logowanie', session })
    await openAccounts()
    await userEvent.click(await screen.findByRole('button', { name: /Anna Nowak/ }))
    expect(await screen.findByText('Strona start')).toBeInTheDocument()
  })

  it('po zalogowaniu wraca na stronę, którą użytkownik chciał otworzyć', async () => {
    renderWithReturnPath(makeSession({ user: null, token: null }), '/poczta')
    await openAccounts()
    await userEvent.click(await screen.findByRole('button', { name: /Anna Nowak/ }))
    expect(await screen.findByText('Poczta')).toBeInTheDocument()
  })

  it('ignoruje zewnętrzny adres powrotu', async () => {
    renderWithReturnPath(makeSession({ user: null, token: null }), '//example.com')
    await openAccounts()
    await userEvent.click(await screen.findByRole('button', { name: /Anna Nowak/ }))
    expect(await screen.findByText('Strona start')).toBeInTheDocument()
  })

  it('pokazuje błąd po polsku, gdy logowanie się nie uda', async () => {
    const session = makeSession({
      user: null,
      token: null,
      login: vi.fn(async () => {
        throw new Error('x')
      }),
    })
    renderWithSession(<Tree />, { route: '/logowanie', session })
    await openAccounts()
    await userEvent.click(await screen.findByRole('button', { name: /Anna Nowak/ }))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/nie udało się zalogować/i))
  })
})


describe('LoginPage — zalogowany', () => {
  it('zalogowany rodzic z rodziną nie widzi logowania, tylko panel', () => {
    markOnboarded(ANNA.id)
    renderWithSession(<Tree />, {
      route: '/logowanie',
      session: makeSession({ family: { family: {}, members: [], children: [], pending_requests: [] } as never }),
    })
    expect(screen.getByText('Strona główna')).toBeInTheDocument()
  })
})
