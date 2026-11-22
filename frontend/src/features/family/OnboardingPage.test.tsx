import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiBlob } from '../../lib/api'
import { isOnboarded } from '../../lib/onboarding'
import type { FamilyView, ParentProfile } from '../../lib/types'
import type { EmploymentDocument } from '../contracts/types'
import { ANNA, makeSession, renderWithSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import OnboardingPage from './OnboardingPage'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
  apiBlob: vi.fn(),
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

const DOC: EmploymentDocument = {
  id: 'umowa-o-prace-kcuw',
  title: 'Umowa o pracę na czas nieokreślony',
  filename: 'umowa-o-prace-kcuw_Nowak_Krakowskie.pdf',
  kind: 'employment',
  employer_name: 'Krakowskie Centrum Usług Wspólnych Sp. z o.o.',
  position: 'Specjalistka ds. kadr i płac',
  fte: 1,
  gross_monthly: 7850,
  start_date: '2021-11-22',
  end_date: null,
  indefinite: true,
  voluntary_sickness: null,
  contract_id: null,
}

const MANDATE: EmploymentDocument = {
  ...DOC,
  id: 'umowa-zlecenia-fundacja',
  title: 'Umowa zlecenia',
  filename: 'umowa-zlecenia-fundacja_Nowak_Fundacja.pdf',
  kind: 'mandate',
  employer_name: 'Fundacja Rodzinny Kraków',
  position: 'Prowadzenie warsztatów dla przyszłych rodziców',
  fte: null,
  gross_monthly: 1200,
  end_date: '2027-03-21',
  indefinite: false,
  voluntary_sickness: true,
}

async function goToContracts() {
  await userEvent.click(screen.getByRole('button', { name: /^dalej/i })) // krok „rodzina” (już istnieje)
  await userEvent.click(await screen.findByRole('button', { name: /^dalej/i })) // dzieci
  await userEvent.click(await screen.findByRole('button', { name: /^dalej/i })) // partner
  return screen.findByRole('heading', { name: /twoje umowy o pracę/i })
}

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

  it('krok 1: „Dołączam do rodziny” z kodem od razu dołącza i przechodzi do dzieci', async () => {
    const mocked = routeApi({
      'POST /api/families/join': { status: 'accepted' },
      'GET /api/profile/me': PROFILE,
    })
    const session = makeSession()
    renderWithSession(<Tree />, { route: '/start', session })
    await userEvent.click(screen.getByRole('button', { name: /dołączam do rodziny/i }))
    const join = screen.getByRole('button', { name: /dołącz do rodziny/i })
    expect(join).toBeDisabled() // bez kodu nie ma czego wysłać
    await userEvent.type(screen.getByLabelText('Kod zaproszenia'), 'ab12cd34')
    await userEvent.click(join)
    await waitFor(() =>
      expect(mocked).toHaveBeenCalledWith('/api/families/join', { method: 'POST', body: { code: 'AB12CD34' } }),
    )
    expect(session.refresh).toHaveBeenCalled()
    expect(await screen.findByRole('heading', { name: /wasze dzieci/i })).toBeInTheDocument()
  })

  it('krok 2: dzieci z rejestrów są zaznaczone, zapisujemy tylko wybrane', async () => {
    const mocked = routeApi({
      'GET /api/profile/me': PROFILE,
      'POST /api/families/me/children': { id: 'c1' },
    })
    renderWithSession(<Tree />, { route: '/start', session: makeSession({ family: FAMILY_VIEW }) })
    await userEvent.click(screen.getByRole('button', { name: /^dalej/i })) // krok „rodzina” (już istnieje)
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

  it('krok 2: dziecko już w rodzinie można odznaczyć — Zapisz zmiany usuwa je z rodziny', async () => {
    const mocked = routeApi({
      'GET /api/profile/me': { ...PROFILE, known_children: [] },
      'DELETE /api/families/me/children/c-maja': undefined,
    })
    const withKid = {
      ...FAMILY_VIEW,
      children: [{ id: 'c-maja', family_id: 'f1', name: 'Maja', status: 'born', birth_date: '2019-05-01', due_date: null }],
    } as unknown as FamilyView
    renderWithSession(<Tree />, { route: '/start', session: makeSession({ family: withKid }) })
    await userEvent.click(screen.getByRole('button', { name: /^dalej/i })) // krok „rodzina”
    const maja = await screen.findByRole('checkbox', { name: /Maja/ })
    expect(maja).toHaveAttribute('aria-checked', 'true')
    expect(maja).not.toHaveAttribute('aria-disabled')
    await userEvent.click(maja)
    expect(maja).toHaveAttribute('aria-checked', 'false')
    await userEvent.click(screen.getByRole('button', { name: /zapisz zmiany/i }))
    await waitFor(() => expect(mocked).toHaveBeenCalledWith('/api/families/me/children/c-maja', { method: 'DELETE' }))
    expect(await screen.findByRole('heading', { name: /zaproś drugiego rodzica/i })).toBeInTheDocument()
  })

  it('krok 3 i 4: kod zaproszenia, potem połączenie Gmaila i przejście do analizy', async () => {
    routeApi({
      'GET /api/profile/me': { ...PROFILE, known_children: [] },
      'GET /api/mail/status': { connected: true, address: 'anna.nowak@gmail.com' },
    })
    renderWithSession(<Tree />, { route: '/start', session: makeSession({ family: FAMILY_VIEW }) })
    await userEvent.click(screen.getByRole('button', { name: /^dalej/i })) // krok „rodzina” (już istnieje)
    await userEvent.click(await screen.findByRole('button', { name: /^dalej/i })) // brak dzieci w rejestrach
    expect(await screen.findByText('Kod zaproszenia: ABCD2345')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /wychowuję dzieci samodzielnie/i }))
    await userEvent.click(screen.getByRole('button', { name: /^dalej/i }))

    expect(await screen.findByRole('heading', { name: /twoje umowy o pracę/i })).toBeInTheDocument()
    await userEvent.click(await screen.findByRole('button', { name: /pomiń na razie/i }))

    expect(await screen.findByRole('heading', { name: /połącz skrzynkę gmail/i })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /połącz z gmail/i }))
    expect(await screen.findByText(/połączono: anna.nowak@gmail.com/i)).toBeInTheDocument()
    expect(isOnboarded(ANNA.id)).toBe(false)
    await userEvent.click(screen.getByRole('button', { name: /sprawdź, co wam przysługuje/i }))
    expect(await screen.findByText('Strona analizy')).toBeInTheDocument()
    expect(isOnboarded(ANNA.id)).toBe(true) // zapamiętane lokalnie — na tym urządzeniu panel otworzy się od razu
  })

  it('rodzina już istnieje (np. z innego urządzenia) — i tak zaczynamy od początku, bez zakładania nowej', async () => {
    const mocked = routeApi({ 'GET /api/profile/me': { ...PROFILE, known_children: [] } })
    renderWithSession(<Tree />, { route: '/start', session: makeSession({ family: FAMILY_VIEW }) })
    expect(screen.getByRole('heading', { name: /zacznijmy od rodziny/i })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /^dalej/i }))
    expect(await screen.findByRole('heading', { name: /wasze dzieci/i })).toBeInTheDocument()
    expect(mocked).not.toHaveBeenCalledWith('/api/families', expect.anything())
  })

  it('Gmail można pominąć', async () => {
    routeApi({ 'GET /api/profile/me': { ...PROFILE, known_children: [] } })
    renderWithSession(<Tree />, { route: '/start', session: makeSession({ family: FAMILY_VIEW }) })
    await userEvent.click(screen.getByRole('button', { name: /^dalej/i })) // krok „rodzina” (już istnieje)
    await userEvent.click(await screen.findByRole('button', { name: /^dalej/i }))
    await userEvent.click(await screen.findByRole('button', { name: /^dalej/i }))
    await userEvent.click(await screen.findByRole('button', { name: /pomiń na razie/i })) // umowy
    expect(await screen.findByRole('heading', { name: /połącz skrzynkę gmail/i })).toBeInTheDocument()
    await userEvent.click(await screen.findByRole('button', { name: /pomiń na razie/i }))
    expect(await screen.findByText('Strona analizy')).toBeInTheDocument()
  })

  it('krok umów: „Załącz umowy” wrzuca UoP i zlecenie, AI je odczytuje, a dane trafiają do umów rodzica', async () => {
    const mocked = routeApi({
      'GET /api/profile/me': { ...PROFILE, known_children: [] },
      'GET /api/contracts/documents': [DOC, MANDATE],
      [`POST /api/contracts/documents/${DOC.id}/import`]: { id: 'contract-1' },
      [`POST /api/contracts/documents/${MANDATE.id}/import`]: { id: 'contract-2' },
    })
    renderWithSession(<Tree />, { route: '/start', session: makeSession({ family: FAMILY_VIEW }) })
    await goToContracts()
    expect(screen.getByText('DANE PRZYKŁADOWE')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /pomiń na razie/i })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /załącz umowy/i }))
    expect(await screen.findByRole('status')).toHaveTextContent(/odczytaliśmy 2 umowy/i)
    for (const d of [DOC, MANDATE]) {
      expect(mocked).toHaveBeenCalledWith(`/api/contracts/documents/${d.id}/import`, { method: 'POST' })
    }
    const uop = screen.getByRole('article', { name: DOC.title })
    expect(uop).toHaveTextContent('Specjalistka ds. kadr i płac')
    expect(uop).toHaveTextContent('pełny etat')
    expect(uop).toHaveTextContent(/na czas nieokreślony/)
    const uz = screen.getByRole('article', { name: 'Umowa zlecenia' })
    expect(uz).toHaveTextContent('Zleceniodawca')
    expect(uz).toHaveTextContent('Fundacja Rodzinny Kraków')
    expect(uz).toHaveTextContent('dobrowolne, opłacane')
    expect(screen.getByText(/bez\s+wynagrodzenia/i)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /^dalej/i }))
    expect(await screen.findByRole('heading', { name: /połącz skrzynkę gmail/i })).toBeInTheDocument()
  })

  it('krok umów: można pominąć bez dodawania, a dodane wcześniej umowy widać od razu z podglądem PDF', async () => {
    const mocked = routeApi({
      'GET /api/profile/me': { ...PROFILE, known_children: [] },
      'GET /api/contracts/documents': [DOC],
    })
    const { unmount } = renderWithSession(<Tree />, {
      route: '/start',
      session: makeSession({ family: FAMILY_VIEW }),
    })
    await goToContracts()
    await userEvent.click(await screen.findByRole('button', { name: /pomiń na razie/i }))
    expect(await screen.findByRole('heading', { name: /połącz skrzynkę gmail/i })).toBeInTheDocument()
    expect(mocked).not.toHaveBeenCalledWith(expect.stringContaining('/import'), expect.anything())
    unmount()

    const win = { location: { href: '' }, close: vi.fn() }
    vi.spyOn(window, 'open').mockReturnValue(win as unknown as Window)
    URL.createObjectURL = vi.fn(() => 'blob:umowa')
    URL.revokeObjectURL = vi.fn()
    vi.mocked(apiBlob).mockResolvedValue(new Blob(['%PDF-1.4'], { type: 'application/pdf' }))
    routeApi({
      'GET /api/profile/me': { ...PROFILE, known_children: [] },
      'GET /api/contracts/documents': [{ ...DOC, contract_id: 'contract-1' }],
    })
    renderWithSession(<Tree />, { route: '/start', session: makeSession({ family: FAMILY_VIEW }) })
    await goToContracts()
    expect(screen.queryByRole('button', { name: /załącz umowy/i })).not.toBeInTheDocument()
    expect(screen.getByRole('article', { name: DOC.title })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /podgląd pdf/i }))
    await waitFor(() => expect(win.location.href).toBe('blob:umowa'))
    expect(apiBlob).toHaveBeenCalledWith(`/api/contracts/documents/${DOC.id}/pdf`)
    expect(screen.getByRole('button', { name: /^dalej/i })).toBeInTheDocument()
  })
})
