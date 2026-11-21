import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AppShell } from '../../components/AppShell'
import type { Child, FamilyView } from '../../lib/types'
import { routeApi } from '../../test/routeApi'
import { ANNA, makeSession, renderWithSession } from '../../test/utils'
import FamilyPage from '../family/FamilyPage'
import JaskolkaHome from './JaskolkaHome'
import { SituationMenu } from './SituationMenu'
import { canUndo, FamilyModeContext, NORMAL_MODE } from './useFamilyMode'
import type { FamilyMode } from './useFamilyMode'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

const FORBIDDEN = [/gratulac/i, /800\s*\+/, /PESEL/i, /plan urlopu/i, /!/]

const MAJA: Child = {
  id: 'c-maja',
  family_id: 'f1',
  name: 'Maja',
  birth_date: '2019-02-01',
  due_date: null,
  status: 'born',
  pesel: null,
  has_disability: false,
  foster: false,
  situation: null,
  situation_kind: null,
  situation_at: null,
  serious_illness: false,
}
const LOST: Child = { ...MAJA, id: 'c-lost', name: 'Dziecko w drodze', birth_date: null, due_date: '2027-01-20', status: 'expected', situation: 'loss', situation_kind: 'poronienie', situation_at: '2026-11-20T10:00:00Z' }

function view(children: Child[]): FamilyView {
  return {
    family: { id: 'f1', name: 'Rodzina Nowak', owner_id: ANNA.id, member_ids: [ANNA.id], invite_code: null, invite_expires_at: null },
    members: [ANNA],
    children,
    pending_requests: [],
  }
}

const IN_WINDOW: FamilyMode = {
  mode: 'jaskolka',
  since: '2026-11-20T10:00:00Z',
  undo_until: new Date(Date.now() + 3 * 86400000).toISOString(),
  child_id: LOST.id,
}
const AFTER_WINDOW: FamilyMode = { ...IN_WINDOW, undo_until: null }

const LOSS_BENEFITS = [
  {
    benefit: {
      id: 'loss-zasilek-pogrzebowy',
      name: 'Zasiłek pogrzebowy z ZUS',
      description: 'Osobie z rodziny, która poniosła koszty pogrzebu, ZUS wypłaca zasiłek.',
      how_to_apply: 'Wniosek składa się w ciągu 12 miesięcy od dnia śmierci.',
      source_url: 'https://www.zus.pl/swiadczenia/zasilki/zasilek-pogrzebowy',
      form_codes: ['ZAM'],
      tags: ['loss_support'],
    },
    match: { status: 'fits' },
  },
  {
    benefit: { id: 'x', name: 'Zwykłe świadczenie', description: 'd', how_to_apply: 'h', source_url: 'https://a.pl', form_codes: [], tags: [] },
    match: { status: 'fits' },
  },
  {
    benefit: { id: 'y', name: 'Niepasujące wsparcie', description: 'd', how_to_apply: 'h', source_url: 'https://a.pl', form_codes: [], tags: ['loss_support'] },
    match: { status: 'no' },
  },
]

const FOUNDATIONS = [
  { id: 'f-1', name: 'Fundacja Nadzieja', description: 'Wsparcie po stracie.', url: 'https://nadzieja.example', situations: ['poronienie'], region: null },
]

function stubFetchForFoundations() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify(FOUNDATIONS), { status: 200, headers: { 'Content-Type': 'application/json' } })),
  )
}

beforeEach(() => stubFetchForFoundations())
afterEach(() => {
  vi.unstubAllGlobals()
  delete document.documentElement.dataset.theme
})

function renderHome(mode: FamilyMode, refresh = vi.fn(async () => {})) {
  return {
    refresh,
    ...renderWithSession(
      <FamilyModeContext.Provider value={{ mode, refresh }}>
        <JaskolkaHome />
      </FamilyModeContext.Provider>,
    ),
  }
}

const BASE_ROUTES = {
  'GET /api/families/me': view([MAJA, LOST]),
  'GET /api/benefits': LOSS_BENEFITS,
  'GET /api/calendar': [
    { id: 'e1', title: 'Zapis Mai do szkoły', due_date: '2027-03-01', child_id: 'c-maja', done: false },
    { id: 'e2', title: 'Termin o utracie', due_date: '2027-03-02', child_id: 'c-lost', done: false },
  ],
}

describe('SituationMenu', () => {
  it('jedno kliknięcie zgłasza zmianę — bez okna potwierdzenia', async () => {
    const api = routeApi({ 'POST /api/families/me/children/c-maja/situation': { ...MAJA, situation: 'loss' } })
    const onChanged = vi.fn()
    const refresh = vi.fn(async () => {})
    renderWithSession(
      <FamilyModeContext.Provider value={{ mode: NORMAL_MODE, refresh }}>
        <SituationMenu child={MAJA} onChanged={onChanged} />
      </FamilyModeContext.Provider>,
    )
    const user = userEvent.setup()
    await user.click(screen.getByText('Zmiana sytuacji'))
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual(['Poronienie', 'Martwe urodzenie', 'Śmierć dziecka'])
    await user.click(screen.getByRole('button', { name: 'Martwe urodzenie' }))

    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.queryByText(/czy na pewno/i)).toBeNull()
    expect(api).toHaveBeenCalledTimes(1)
    expect(api).toHaveBeenCalledWith('/api/families/me/children/c-maja/situation', { method: 'POST', body: { kind: 'martwe-urodzenie' } })
    await waitFor(() => expect(onChanged).toHaveBeenCalled())
    expect(refresh).toHaveBeenCalled()
  })

  it('dla dziecka w sytuacji nic nie renderuje', () => {
    routeApi({})
    const { container } = renderWithSession(<SituationMenu child={LOST} onChanged={vi.fn()} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('błąd pokazuje spokojny komunikat', async () => {
    const { ApiError } = await import('../../lib/api')
    routeApi({ 'POST /api/families/me/children/c-maja/situation': new ApiError(404, 'Nie znaleziono takiego dziecka.') })
    renderWithSession(<SituationMenu child={MAJA} onChanged={vi.fn()} />)
    const user = userEvent.setup()
    await user.click(screen.getByText('Zmiana sytuacji'))
    await user.click(screen.getByRole('button', { name: 'Poronienie' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Nie znaleziono takiego dziecka.')
  })
})

describe('JaskolkaHome', () => {
  it('pokazuje listę „Dla Was”: tylko świadczenia o stracie z wnioskami wstępnie wypełnionymi', async () => {
    routeApi(BASE_ROUTES)
    renderHome(IN_WINDOW)
    expect(await screen.findByRole('heading', { name: 'Zasiłek pogrzebowy z ZUS' })).toBeInTheDocument()
    expect(screen.queryByText('Zwykłe świadczenie')).toBeNull() // bez tagu loss_support
    expect(screen.queryByText('Niepasujące wsparcie')).toBeNull() // match.status === no
    const apply = screen.getByRole('link', { name: 'Przygotuj wniosek (ZAM)' })
    expect(apply).toHaveAttribute('href', '/wnioski/nowy?form=ZAM')
    expect(screen.getByText(/wypełnimy z danych z Waszego profilu/)).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: /Fundacja Nadzieja/ })).toHaveAttribute('href', 'https://nadzieja.example')
    expect(screen.getByRole('link', { name: 'Pełna lista kroków i dokumentów' })).toHaveAttribute('href', '/jaskolka/poronienie')
  })

  it('nie renderuje zakazanych treści („gratulacje”, 800+, PESEL, plan urlopu, wykrzykniki)', async () => {
    routeApi(BASE_ROUTES)
    const { container } = renderHome(IN_WINDOW)
    await screen.findByRole('heading', { name: 'Zasiłek pogrzebowy z ZUS' })
    await screen.findByRole('link', { name: /Fundacja Nadzieja/ })
    const text = container.textContent ?? ''
    for (const re of FORBIDDEN) expect(text, String(re)).not.toMatch(re)
  })

  it('terminy innych dzieci są wyciszone, a o dziecku w sytuacji nie ma ani słowa', async () => {
    routeApi(BASE_ROUTES)
    renderHome(IN_WINDOW)
    const section = (await screen.findByRole('heading', { name: 'Terminy pozostałych dzieci' })).closest('section') as HTMLElement
    expect(within(section).getByText(/Zapis Mai do szkoły/)).toBeInTheDocument()
    expect(within(section).getByText(/do 01\.03\.2027/)).toBeInTheDocument()
    expect(within(section).queryByText(/Termin o utracie/)).toBeNull()
  })

  it('cofnięcie widać tylko w oknie i działa jednym kliknięciem', async () => {
    const api = routeApi({ ...BASE_ROUTES, 'DELETE /api/families/me/children/c-lost/situation': { ...LOST, situation: null } })
    const { refresh } = renderHome(IN_WINDOW)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Cofnij zgłoszenie' }))
    expect(api).toHaveBeenCalledWith('/api/families/me/children/c-lost/situation', { method: 'DELETE' })
    await waitFor(() => expect(refresh).toHaveBeenCalled())
  })

  it('po upływie okna nie ma „Cofnij zgłoszenie”, jest tylko wyjście z trybu', async () => {
    const api = routeApi({ ...BASE_ROUTES, 'POST /api/families/me/mode/exit': undefined })
    const { refresh } = renderHome(AFTER_WINDOW)
    await screen.findByRole('heading', { name: 'Zasiłek pogrzebowy z ZUS' })
    expect(screen.queryByRole('button', { name: 'Cofnij zgłoszenie' })).toBeNull()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Wróć do zwykłego widoku' }))
    expect(api).toHaveBeenCalledWith('/api/families/me/mode/exit', { method: 'POST' })
    await waitFor(() => expect(refresh).toHaveBeenCalled())
  })

  it('brak benefit/calendar API nie psuje strony (sekcje się nie pokazują)', async () => {
    routeApi({ 'GET /api/families/me': view([MAJA, LOST]) }) // /api/benefits i /api/calendar → 404 z atrapy
    renderHome(IN_WINDOW)
    expect(await screen.findByText(/Na razie nie ma tu pozycji do pokazania/)).toBeInTheDocument()
    expect(screen.queryByText('Terminy pozostałych dzieci')).toBeNull()
    expect(screen.getByRole('button', { name: 'Wróć do zwykłego widoku' })).toBeInTheDocument()
  })

  it('canUndo uwzględnia okno', () => {
    expect(canUndo(IN_WINDOW)).toBe(true)
    expect(canUndo(AFTER_WINDOW)).toBe(false)
    expect(canUndo(NORMAL_MODE)).toBe(false)
    expect(canUndo({ ...IN_WINDOW, undo_until: '2020-01-01T00:00:00Z' })).toBe(false)
  })
})

describe('AppShell w trybie jaskółki', () => {
  function tree() {
    return (
      <Routes>
        <Route path="/start" element={<p>Onboarding</p>} />
        <Route element={<AppShell />}>
          <Route path="/" element={<p>Panel z kolorowymi kafelkami</p>} />
          <Route path="/rodzina" element={<p>Strona rodziny</p>} />
        </Route>
      </Routes>
    )
  }
  const session = () => makeSession({ family: view([MAJA, LOST]) })

  it('ustawia motyw mono i pokazuje „Dla Was” zamiast panelu', async () => {
    routeApi({ ...BASE_ROUTES, 'GET /api/me/mode': IN_WINDOW })
    renderWithSession(tree(), { route: '/', session: session() })
    expect(await screen.findByRole('heading', { name: 'Dla Was' })).toBeInTheDocument()
    expect(screen.queryByText('Panel z kolorowymi kafelkami')).toBeNull()
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('mono'))
  })

  it('inne strony działają normalnie także w trybie', async () => {
    routeApi({ ...BASE_ROUTES, 'GET /api/me/mode': IN_WINDOW })
    renderWithSession(tree(), { route: '/rodzina', session: session() })
    expect(await screen.findByText('Strona rodziny')).toBeInTheDocument()
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('mono'))
  })

  it('w trybie normalnym pokazuje panel i nie rusza motywu', async () => {
    routeApi({ 'GET /api/me/mode': NORMAL_MODE })
    renderWithSession(tree(), { route: '/', session: session() })
    expect(await screen.findByText('Panel z kolorowymi kafelkami')).toBeInTheDocument()
    expect(document.documentElement.dataset.theme).toBeUndefined()
  })

  it('bez rodziny nie pyta o tryb (kieruje do onboardingu)', () => {
    const api = routeApi({})
    renderWithSession(tree(), { route: '/', session: makeSession() })
    expect(screen.getByText('Onboarding')).toBeInTheDocument()
    expect(api).not.toHaveBeenCalled()
  })

  it('przywraca poprzedni motyw po wyjściu z trybu', async () => {
    const api = routeApi({ ...BASE_ROUTES, 'GET /api/me/mode': IN_WINDOW, 'POST /api/families/me/mode/exit': undefined })
    renderWithSession(tree(), { route: '/', session: session() })
    await screen.findByRole('heading', { name: 'Dla Was' })
    api.mockImplementation((async (path: string, init?: { method?: string }) => {
      if (path === '/api/me/mode') return NORMAL_MODE
      if (path === '/api/families/me') return view([MAJA, LOST])
      if (path === '/api/benefits') return LOSS_BENEFITS
      if (path === '/api/families/me/mode/exit' && init?.method === 'POST') return undefined
      throw new Error(`nieoczekiwane ${path}`)
    }) as never)
    await userEvent.setup().click(screen.getByRole('button', { name: 'Wróć do zwykłego widoku' }))
    expect(await screen.findByText('Panel z kolorowymi kafelkami')).toBeInTheDocument()
    expect(document.documentElement.dataset.theme).toBeUndefined()
  })
})

describe('FamilyPage: zmiana sytuacji i „Za życiem”', () => {
  it('karta dziecka ma spokojną opcję „Zmiana sytuacji”; dziecko w sytuacji — tylko dyskretną informację', async () => {
    routeApi({ 'GET /api/families/me': view([MAJA, LOST]) })
    renderWithSession(<FamilyPage />, { session: makeSession({ family: view([MAJA, LOST]) }) })
    const user = userEvent.setup()
    expect(await screen.findByRole('heading', { name: 'Maja' })).toBeInTheDocument()
    expect(screen.getByText('Jesteśmy z Wami')).toBeInTheDocument() // dziecko w sytuacji: tylko dyskretna informacja
    await user.click(screen.getByRole('button', { name: 'Ustawienia: Maja' }))
    expect(screen.getByText('Zmiana sytuacji')).toBeInTheDocument()
    expect(screen.getByRole('switch', { name: /ciężka, nieodwracalna choroba/i })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Zamknij' }))
    await user.click(screen.getByRole('button', { name: 'Ustawienia: Maleństwo' }))
    expect(screen.getByText(/Zmiana sytuacji została zapisana/)).toBeInTheDocument()
    expect(screen.queryByText('Zmiana sytuacji')).toBeNull()
    expect(screen.queryByRole('switch')).toBeNull()
  })

  it('flaga „Za życiem” zapisuje się i pokazuje komunikat o dodanych świadczeniach', async () => {
    let ill = false
    const api = routeApi({
      'GET /api/families/me': () => view([{ ...MAJA, serious_illness: ill }]),
      'PATCH /api/families/me/children/c-maja/serious-illness': (init?: { body?: unknown }) => {
        ill = Boolean((init?.body as { value?: boolean } | undefined)?.value)
        return { ...MAJA, serious_illness: ill }
      },
    })
    renderWithSession(<FamilyPage />, { session: makeSession({ family: view([MAJA]) }) })
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Ustawienia: Maja' }))
    await user.click(screen.getByRole('switch', { name: /ciężka, nieodwracalna choroba/i }))
    expect(api).toHaveBeenCalledWith('/api/families/me/children/c-maja/serious-illness', { method: 'PATCH', body: { value: true } })
    expect(await screen.findByText(/Dodaliśmy świadczenia z programu „Za życiem”/)).toBeInTheDocument()
  })
})
