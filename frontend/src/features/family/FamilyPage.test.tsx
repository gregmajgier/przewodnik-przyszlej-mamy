import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { FamilyView } from '../../lib/types'
import { ANNA, makeSession, renderWithSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import { fetchSituation } from '../jaskolka/jaskolkaApi'
import type { SituationDetail } from '../jaskolka/jaskolkaApi'
import FamilyPage from './FamilyPage'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

// checklisty sytuacji (/api/jaskolka/situations/{id}) idą przez fetch, nie przez `api`
vi.mock('../jaskolka/jaskolkaApi', async (orig) => ({
  ...(await orig<typeof import('../jaskolka/jaskolkaApi')>()),
  fetchSituation: vi.fn(),
}))

const PIOTR = { ...ANNA, id: 'user-nowak-piotr', name: 'Piotr Nowak' }

function view(over: Partial<FamilyView> = {}): FamilyView {
  return {
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
    ...over,
  }
}

describe('FamilyPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('pokazuje prośbę pending i wywołuje accept', async () => {
    const pending = view({
      pending_requests: [
        { id: 'jr-1', family_id: 'f1', user_id: PIOTR.id, status: 'pending', user_name: 'Piotr Nowak' },
      ],
    })
    const accepted = view({
      family: { ...pending.family, member_ids: [ANNA.id, PIOTR.id] },
      members: [ANNA, PIOTR],
    })
    let current = pending
    const mocked = routeApi({
      'GET /api/families/me': () => current,
      'POST /api/families/me/join-requests/jr-1/accept': () => {
        current = accepted
        return accepted
      },
    })
    const session = makeSession()
    renderWithSession(<FamilyPage />, { session })
    expect(await screen.findByText(/chce dołączyć/i)).toBeInTheDocument()
    expect(screen.getByText('Piotr Nowak')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /akceptuj/i }))
    await waitFor(() =>
      expect(mocked).toHaveBeenCalledWith('/api/families/me/join-requests/jr-1/accept', {
        method: 'POST',
      }),
    )
    await waitFor(() => expect(screen.queryByText(/chce dołączyć/i)).not.toBeInTheDocument())
    expect(session.refresh).toHaveBeenCalled()
  })

  it('odrzucenie wywołuje reject', async () => {
    const pending = view({
      pending_requests: [
        { id: 'jr-1', family_id: 'f1', user_id: PIOTR.id, status: 'pending', user_name: 'Piotr Nowak' },
      ],
    })
    const mocked = routeApi({
      'GET /api/families/me': pending,
      'POST /api/families/me/join-requests/jr-1/reject': view(),
    })
    renderWithSession(<FamilyPage />)
    await userEvent.click(await screen.findByRole('button', { name: /odrzuć/i }))
    expect(mocked).toHaveBeenCalledWith('/api/families/me/join-requests/jr-1/reject', {
      method: 'POST',
    })
  })

  it('pokazuje członków, kod zaproszenia i dzieci (w tym dziecko w drodze)', async () => {
    routeApi({
      'GET /api/families/me': view({
        children: [
          {
            id: 'c1',
            family_id: 'f1',
            name: 'Maja',
            birth_date: '2019-05-01',
            due_date: null,
            status: 'born',
          } as never,
          {
            id: 'c2',
            family_id: 'f1',
            name: 'Maluszek',
            birth_date: null,
            due_date: '2027-01-20',
            status: 'expected',
          } as never,
        ],
      }),
    })
    renderWithSession(<FamilyPage />)
    expect(await screen.findByText('ABCD2345')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Maja' })).toBeInTheDocument()
    expect(screen.getByText(/w drodze · termin 20\.01\.2027/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Anna Nowak/ })).toHaveAttribute('href', `/sprawy/${ANNA.id}`)
  })

  it('błąd pobrania rodziny pokazuje komunikat', async () => {
    const { ApiError } = await import('../../lib/api')
    routeApi({ 'GET /api/families/me': new ApiError(500, 'Coś poszło nie tak po naszej stronie.') })
    renderWithSession(<FamilyPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/coś poszło nie tak/i)
  })

  it('dodanie dziecka w arkuszu: imię, „w drodze”, termin w formacie DD.MM.RRRR', async () => {
    const mocked = routeApi({ 'GET /api/families/me': view(), 'POST /api/families/me/children': { id: 'c9' } })
    renderWithSession(<FamilyPage />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: /dodaj dziecko/i }))
    const sheet = await screen.findByRole('dialog', { name: /dodaj dziecko/i })
    await new Promise((r) => setTimeout(r, 50)) // arkusz ustawia fokus na pierwszym polu
    await user.click(within(sheet).getByRole('tab', { name: /w drodze/i }))
    await user.type(within(sheet).getByLabelText('Imię'), 'Zosia')
    await user.type(within(sheet).getByLabelText(/termin porodu/i), '20012027')
    const save = within(sheet).getByRole('button', { name: /^dodaj dziecko$/i })
    await waitFor(() => expect(save).toBeEnabled())
    await user.click(save)
    await waitFor(() =>
      expect(mocked).toHaveBeenCalledWith('/api/families/me/children', {
        method: 'POST',
        body: { name: 'Zosia', birth_date: null, due_date: '2027-01-20' },
      }),
    )
  })
})

// ---------- „Ciężka sytuacja”: instrukcja z menu, nowe wnioski po zgłoszeniu, cofanie ----------

const KID = {
  id: 'c1',
  family_id: 'f1',
  name: 'Maja',
  birth_date: '2026-11-01',
  due_date: null,
  status: 'born',
  pesel: null,
  has_disability: false,
  foster: false,
  situation: null,
  situation_kind: null,
  situation_at: null,
  serious_illness: false,
} as const
const LOST_KID = { ...KID, situation: 'loss', situation_kind: 'poronienie', situation_at: '2026-11-20T10:00:00Z' } as const

function checklist(id: string, codes: string[][]): SituationDetail {
  return {
    id,
    label: id,
    intro: '',
    checklist: codes.map((form_codes, i) => ({
      id: `${id}-${i}`,
      title: 't',
      body: 'b',
      kind: 'right',
      deadline_text: null,
      form_codes,
      source_url: 'https://www.gov.pl/x',
      verify: false,
    })),
  }
}

// te same kody co w backend/app/data/jaskolka.json
const SITUATIONS: Record<string, SituationDetail> = {
  poronienie: checklist('poronienie', [[], ['ZAM'], [], ['Z-12']]),
  'smierc-dziecka': checklist('smierc-dziecka', [[], [], ['Z-12']]),
  'ciezka-choroba': checklist('ciezka-choroba', [['ZA-ZYCIEM'], []]),
}

const FORM_ROUTES = {
  'GET /api/wnioski': [
    { kod: 'ZAM', nazwa: 'Wniosek o zasiłek macierzyński', instytucja: 'ZUS lub płatnik', plik_lokalny: null },
    { kod: 'Z-12', nazwa: 'Wniosek o zasiłek pogrzebowy', instytucja: 'ZUS', plik_lokalny: 'wnioski_pdf/Z-12_pdf_do_druku.pdf' },
    { kod: 'ZA-ZYCIEM', nazwa: 'Wniosek o jednorazowe świadczenie 4000 zł (Za życiem)', instytucja: 'gmina', plik_lokalny: null },
  ],
  'GET /api/applications/forms': { forms: [{ code: 'ZAM' }, { code: 'ZA-ZYCIEM' }], recommended_flow: [] },
  'GET /api/benefits': [],
}

/** Rodzina z jednym dzieckiem; POST/DELETE sytuacji i PATCH „Za życiem” zmieniają to, co zwraca GET. */
function familyRoutes(start: object = KID, extra: Record<string, unknown> = {}) {
  let kid: object = start
  return routeApi({
    ...FORM_ROUTES,
    'GET /api/families/me': () => view({ children: [kid as never] }),
    'POST /api/families/me/children/c1/situation': (init?: { body?: unknown }) => {
      const { kind } = (init?.body ?? {}) as { kind?: string }
      kid = { ...KID, situation: 'loss', situation_kind: kind, situation_at: '2026-11-22T10:00:00Z' }
      return kid
    },
    'DELETE /api/families/me/children/c1/situation': () => {
      kid = KID
      return kid
    },
    'PATCH /api/families/me/children/c1/serious-illness': (init?: { body?: unknown }) => {
      const { value } = (init?.body ?? {}) as { value?: boolean }
      kid = { ...KID, serious_illness: Boolean(value) }
      return kid
    },
    ...extra,
  })
}

async function report(kind: 'Poronienie' | 'Śmierć dziecka') {
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: 'Ustawienia: Maja' }))
  await user.click(screen.getByText('Zmiana sytuacji'))
  await user.click(screen.getByRole('button', { name: kind }))
  return user
}

describe('FamilyPage: ciężka sytuacja', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(fetchSituation).mockImplementation(async (id: string) => SITUATIONS[id])
  })

  it('wejście z menu konta pokazuje na górze instrukcję, skrót do karty dziecka i da się ją zamknąć', async () => {
    familyRoutes()
    renderWithSession(<FamilyPage />, { route: { pathname: '/rodzina', state: { hardSituation: true } } })
    const heading = await screen.findByRole('heading', { name: 'Jak zgłosić trudną sytuację' })
    await waitFor(() => expect(heading).toHaveFocus())
    const help = heading.closest('section') as HTMLElement
    expect(within(help).getByText(/Rozwiń „Zmiana sytuacji”/)).toBeInTheDocument()
    expect(within(help).getByText(/możesz cofnąć w każdej chwili/)).toBeInTheDocument()
    expect(help.textContent).not.toContain('!')

    const user = userEvent.setup()
    await user.click(within(help).getByRole('button', { name: 'Otwórz kartę: Maja' }))
    expect(screen.getByRole('switch', { name: /ciężka, nieodwracalna choroba/i })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Zamknij' }))

    await user.click(within(help).getByRole('button', { name: 'Zamknij instrukcję' }))
    expect(screen.queryByRole('heading', { name: 'Jak zgłosić trudną sytuację' })).toBeNull()
  })

  it('bez wejścia z menu instrukcji nie ma', async () => {
    familyRoutes()
    renderWithSession(<FamilyPage />, { route: '/rodzina' })
    expect(await screen.findByRole('heading', { name: 'Maja' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Jak zgłosić trudną sytuację' })).toBeNull()
  })

  it('poronienie → „możesz złożyć 2 wnioski”: ZAM z kreatorem, Z-12 jako pusty PDF', async () => {
    const api = familyRoutes()
    renderWithSession(<FamilyPage />)
    await report('Poronienie')
    expect(api).toHaveBeenCalledWith('/api/families/me/children/c1/situation', { method: 'POST', body: { kind: 'poronienie' } })
    expect(await screen.findByText('Po tym zgłoszeniu możesz złożyć 2 wnioski:')).toBeInTheDocument()
    expect(screen.getByText(/Wniosek o zasiłek macierzyński/)).toHaveTextContent('Wniosek o zasiłek macierzyński (ZAM)')
    expect(screen.getByRole('link', { name: 'Przygotuj wniosek' })).toHaveAttribute('href', '/wnioski/nowy?form=ZAM&child=c1')
    expect(screen.getByRole('link', { name: /Pobierz pusty wniosek/ }).getAttribute('href')).toMatch(/\/api\/wnioski\/Z-12\/pdf$/)
    expect(screen.getByRole('button', { name: 'Cofnij zgłoszenie' })).toBeInTheDocument()
  })

  it('śmierć dziecka → 1 wniosek (Z-12); ZAM znika, gdy dopasowanie mówi „nie”', async () => {
    familyRoutes(KID, { 'GET /api/benefits': [{ benefit: { form_codes: ['ZAM'] }, match: { status: 'no' } }] })
    renderWithSession(<FamilyPage />)
    await report('Śmierć dziecka')
    expect(await screen.findByText('Po tym zgłoszeniu możesz złożyć 1 wniosek:')).toBeInTheDocument()
    expect(screen.getByText(/Wniosek o zasiłek pogrzebowy/)).toHaveTextContent('Wniosek o zasiłek pogrzebowy (Z-12)')
    expect(screen.queryByText(/ZAM/)).toBeNull()
  })

  it('„Za życiem” → komunikat z wnioskiem ZA-ZYCIEM; wyłączenie chowa komunikat', async () => {
    familyRoutes()
    renderWithSession(<FamilyPage />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Ustawienia: Maja' }))
    await user.click(screen.getByRole('switch', { name: /ciężka, nieodwracalna choroba/i }))
    expect(await screen.findByText('Po tym zgłoszeniu możesz złożyć 1 wniosek:')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Przygotuj wniosek' })).toHaveAttribute('href', '/wnioski/nowy?form=ZA-ZYCIEM&child=c1')
    await user.click(screen.getByRole('switch', { name: /ciężka, nieodwracalna choroba/i }))
    await waitFor(() => expect(screen.queryByText(/możesz złożyć/)).toBeNull())
  })

  it('zgłoszoną stratę da się cofnąć w każdej chwili z karty dziecka', async () => {
    const api = familyRoutes(LOST_KID)
    renderWithSession(<FamilyPage />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Ustawienia: Maja' }))
    expect(screen.getByText(/Zmiana sytuacji została zapisana/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Cofnij zgłoszenie' }))
    expect(api).toHaveBeenCalledWith('/api/families/me/children/c1/situation', { method: 'DELETE' })
    // po cofnięciu karta wraca do zwykłych opcji
    expect(await screen.findByRole('switch', { name: /ciężka, nieodwracalna choroba/i })).toBeInTheDocument()
    expect(screen.getByText('Zmiana sytuacji')).toBeInTheDocument()
  })
})
