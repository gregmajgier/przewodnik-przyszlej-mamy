import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { FamilyView, ParentProfile } from '../../lib/types'
import { ANNA, makeSession, renderWithSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import OnboardingPage from './OnboardingPage'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

const PROFILE = {
  user_id: ANNA.id,
  known_children: [
    { name: 'Maja', birth_date: '2019-05-01', due_date: null },
    { name: 'Dziecko w drodze', birth_date: null, due_date: '2027-01-20' },
  ],
} as ParentProfile

const FAMILY_VIEW = {
  family: {
    id: 'f1',
    name: 'Rodzina Nowak',
    owner_id: ANNA.id,
    member_ids: [ANNA.id],
    invite_code: 'ABCD2345',
    invite_expires_at: null,
  },
  members: [ANNA],
  children: [],
  pending_requests: [],
} as FamilyView

function Tree() {
  return (
    <Routes>
      <Route path="/start" element={<OnboardingPage />} />
      <Route path="/analiza" element={<p>Strona analizy</p>} />
      <Route path="/rodzina" element={<p>Strona rodziny</p>} />
      <Route path="/dolacz" element={<p>Strona dołączania</p>} />
    </Routes>
  )
}

describe('OnboardingPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('krok 1: domyślnie „Zakładam rodzinę” — Dalej zakłada rodzinę i przechodzi do dzieci', async () => {
    const mocked = routeApi({
      'POST /api/families': FAMILY_VIEW,
      'GET /api/profile/me': PROFILE,
    })
    const session = makeSession()
    renderWithSession(<Tree />, { route: '/start', session })
    expect(screen.getByRole('button', { name: /zakładam rodzinę/i })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: /^dalej/i }))
    await waitFor(() => expect(mocked).toHaveBeenCalledWith('/api/families', { method: 'POST', body: {} }))
    expect(session.refresh).toHaveBeenCalled()
    expect(await screen.findByRole('heading', { name: /wasze dzieci/i })).toBeInTheDocument()
  })

  it('krok 1: „Dołączam do rodziny” prowadzi do wpisania kodu', async () => {
    routeApi({})
    renderWithSession(<Tree />, { route: '/start', session: makeSession() })
    await userEvent.click(screen.getByRole('button', { name: /dołączam do rodziny/i }))
    await userEvent.click(screen.getByRole('button', { name: /^dalej/i }))
    expect(await screen.findByText('Strona dołączania')).toBeInTheDocument()
  })

  it('krok 2: dzieci z rejestrów są zaznaczone, zapisujemy tylko wybrane', async () => {
    const mocked = routeApi({
      'GET /api/profile/me': PROFILE,
      'POST /api/families/me/children': { id: 'c1' },
    })
    renderWithSession(<Tree />, { route: '/start', session: makeSession({ family: FAMILY_VIEW }) })
    const maja = await screen.findByRole('checkbox', { name: /Maja/ })
    expect(maja).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('checkbox', { name: /Dziecko w drodze/ })).toHaveAttribute('aria-checked', 'true')
    await userEvent.click(maja) // odznacz Maję
    await userEvent.click(screen.getByRole('button', { name: /dodaj dzieci \(1\)/i }))
    await waitFor(() =>
      expect(mocked).toHaveBeenCalledWith('/api/families/me/children', {
        method: 'POST',
        body: { name: 'Dziecko w drodze', birth_date: null, due_date: '2027-01-20' },
      }),
    )
    expect(mocked).not.toHaveBeenCalledWith(
      '/api/families/me/children',
      expect.objectContaining({ body: expect.objectContaining({ name: 'Maja' }) }),
    )
    expect(await screen.findByRole('heading', { name: /zaproś drugiego rodzica/i })).toBeInTheDocument()
  })

  it('krok 3 i 4: kod zaproszenia, potem połączenie Gmaila i przejście do analizy', async () => {
    routeApi({
      'GET /api/profile/me': { ...PROFILE, known_children: [] },
      'GET /api/mail/status': { connected: true, address: 'anna.nowak@gmail.com' },
    })
    renderWithSession(<Tree />, { route: '/start', session: makeSession({ family: FAMILY_VIEW }) })
    await userEvent.click(await screen.findByRole('button', { name: /^dalej/i })) // brak dzieci w rejestrach
    expect(await screen.findByText('Kod zaproszenia: ABCD2345')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /wychowuję dzieci samodzielnie/i }))
    await userEvent.click(screen.getByRole('button', { name: /^dalej/i }))

    expect(await screen.findByRole('heading', { name: /połącz skrzynkę gmail/i })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /połącz z gmail/i }))
    expect(await screen.findByText(/połączono: anna.nowak@gmail.com/i)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /sprawdź, co wam przysługuje/i }))
    expect(await screen.findByText('Strona analizy')).toBeInTheDocument()
  })

  it('Gmail można pominąć', async () => {
    routeApi({ 'GET /api/profile/me': { ...PROFILE, known_children: [] } })
    renderWithSession(<Tree />, { route: '/start', session: makeSession({ family: FAMILY_VIEW }) })
    await userEvent.click(await screen.findByRole('button', { name: /^dalej/i }))
    await userEvent.click(await screen.findByRole('button', { name: /^dalej/i }))
    await userEvent.click(await screen.findByRole('button', { name: /pomiń na razie/i }))
    expect(await screen.findByText('Strona analizy')).toBeInTheDocument()
  })
})
