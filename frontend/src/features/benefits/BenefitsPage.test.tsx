import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../lib/api'
import type { FamilyView } from '../../lib/types'
import { ANNA, makeSession, renderWithSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import BenefitsPage from './BenefitsPage'
import type { Benefit, BenefitMatch } from './types'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

const FAMILY = {
  family: { id: 'f1', name: 'Nowak', owner_id: ANNA.id, member_ids: [ANNA.id], invite_code: null, invite_expires_at: null },
  members: [ANNA],
  children: [],
  pending_requests: [],
} as FamilyView

function benefit(over: Partial<Benefit>): Benefit {
  return {
    id: 'b',
    name: 'Świadczenie',
    scope: 'national',
    unit_id: null,
    category: 'benefit',
    description: '',
    amount_text: null,
    annual_value_estimate: null,
    how_to_apply: '',
    form_codes: [],
    source_url: 'https://www.gov.pl/zrodlo',
    extra_text: null,
    verify: false,
    ...over,
  }
}

const FITS: BenefitMatch = {
  benefit: benefit({ id: 'nat-800', name: '800 plus', amount_text: '800 zł miesięcznie', form_codes: ['800PLUS'] }),
  match: { status: 'fits', reasons: ['pasuje, bo dziecko ma 3 lata i mieszkasz w Krakowie'], unmet: [], questions: [] },
}
const MAYBE: BenefitMatch = {
  benefit: benefit({ id: 'nat-kdr', name: 'Karta Dużej Rodziny', form_codes: ['KDR'] }),
  match: {
    status: 'maybe',
    reasons: ['masz troje dzieci'],
    unmet: [],
    questions: [{ condition_id: 'income', text: 'Czy dochód na osobę jest niższy niż 1922 zł?' }],
  },
}
const NO: BenefitMatch = {
  benefit: benefit({ id: 'nat-za-zyciem', name: 'Za życiem', form_codes: ['ZA-ZYCIEM'], verify: true }),
  match: { status: 'no', reasons: [], unmet: ['dziecko nie ma orzeczenia o niepełnosprawności'], questions: [] },
}

function Tree() {
  return (
    <Routes>
      <Route path="/swiadczenia" element={<BenefitsPage />} />
      <Route path="/start" element={<p>Start</p>} />
      <Route path="/wnioski/nowy" element={<p>Kreator wniosku</p>} />
    </Routes>
  )
}

function renderPage(family: FamilyView | null = FAMILY) {
  return renderWithSession(<Tree />, { route: '/swiadczenia', session: makeSession({ family }) })
}

describe('BenefitsPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('„Dla Was” pokazuje to, co pasuje; „Sprawdź” — do sprawdzenia; „Wszystkie” — także niepasujące', async () => {
    routeApi({ 'GET /api/benefits': [FITS, MAYBE, NO] })
    renderPage()
    const list = await screen.findByRole('region', { name: /przeglądaj świadczenia/i })
    expect(within(list).getByRole('button', { name: /800 plus/i })).toBeInTheDocument()
    expect(within(list).queryByRole('button', { name: /karta dużej rodziny/i })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('tab', { name: /sprawdź/i }))
    expect(within(list).getByRole('button', { name: /karta dużej rodziny/i })).toBeInTheDocument()
    expect(within(list).queryByRole('button', { name: /800 plus/i })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('tab', { name: /wszystkie/i }))
    expect(within(list).getByRole('button', { name: /za życiem.*nie pasuje/i })).toBeInTheDocument()
  })

  it('kafelki podsumowania od razu filtrują listę pasujących i wymagających sprawdzenia', async () => {
    routeApi({ 'GET /api/benefits': [FITS, MAYBE, NO] })
    renderPage()
    const list = await screen.findByRole('region', { name: /przeglądaj świadczenia/i })

    await userEvent.click(screen.getByRole('button', { name: /pokaż świadczenia do sprawdzenia/i }))
    expect(within(list).getByRole('button', { name: /karta dużej rodziny/i })).toBeInTheDocument()
    expect(within(list).queryByRole('button', { name: /800 plus/i })).not.toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /sprawdź/i })).toHaveAttribute('aria-selected', 'true')

    await userEvent.click(screen.getByRole('button', { name: /pokaż świadczenia, które pasują do was/i }))
    expect(within(list).getByRole('button', { name: /800 plus/i })).toBeInTheDocument()
    expect(within(list).queryByRole('button', { name: /karta dużej rodziny/i })).not.toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /dla was/i })).toHaveAttribute('aria-selected', 'true')
  })

  it('szczegóły w arkuszu: dlaczego pasuje, „Złóż wniosek” do kreatora i źródło w nowej karcie', async () => {
    routeApi({ 'GET /api/benefits': [FITS, MAYBE, NO] })
    renderPage()
    const list = await screen.findByRole('region', { name: /przeglądaj świadczenia/i })
    await userEvent.click(within(list).getByRole('button', { name: /800 plus/i }))
    const sheet = screen.getByRole('dialog', { name: '800 plus' })
    expect(within(sheet).getByText(/dziecko ma 3 lata/)).toBeInTheDocument()
    expect(within(sheet).getByRole('link', { name: /złóż wniosek/i })).toHaveAttribute('href', '/wnioski/nowy?form=800PLUS')
    const source = within(sheet).getByRole('link', { name: /oficjalne źródło/i })
    expect(source).toHaveAttribute('href', 'https://www.gov.pl/zrodlo')
    expect(source).toHaveAttribute('target', '_blank')
    await userEvent.click(within(sheet).getByRole('link', { name: /złóż wniosek/i }))
    expect(await screen.findByText('Kreator wniosku')).toBeInTheDocument()
  })

  it('niepasujące: powód „dlaczego nie” i brak przycisku wniosku', async () => {
    routeApi({ 'GET /api/benefits': [NO] })
    renderPage()
    await userEvent.click(await screen.findByRole('tab', { name: /wszystkie/i }))
    await userEvent.click(screen.getByRole('button', { name: /za życiem/i }))
    const sheet = screen.getByRole('dialog', { name: 'Za życiem' })
    expect(within(sheet).getByText(/dlaczego nie teraz/i)).toBeInTheDocument()
    expect(within(sheet).getByText(/nie ma orzeczenia/)).toBeInTheDocument()
    expect(within(sheet).queryByRole('link', { name: /złóż wniosek/i })).not.toBeInTheDocument()
  })

  it('odpowiedź tak/nie zapisuje się przez API i przelicza dopasowanie', async () => {
    const updated: BenefitMatch = { ...MAYBE, match: { ...MAYBE.match, status: 'fits', questions: [] } }
    const mocked = routeApi({ 'GET /api/benefits': [FITS, MAYBE], 'POST /api/benefits/nat-kdr/answers': updated })
    renderPage()
    await userEvent.click(await screen.findByRole('tab', { name: /sprawdź/i }))
    await userEvent.click(screen.getByRole('button', { name: /karta dużej rodziny/i }))
    const sheet = screen.getByRole('dialog', { name: 'Karta Dużej Rodziny' })
    expect(within(sheet).getByText(/dochód na osobę/)).toBeInTheDocument()
    await userEvent.click(within(sheet).getByRole('button', { name: 'Tak' }))
    await waitFor(() =>
      expect(mocked).toHaveBeenCalledWith('/api/benefits/nat-kdr/answers', { method: 'POST', body: { condition_id: 'income', answer: true } }),
    )
    await waitFor(() => expect(within(sheet).queryByText(/dochód na osobę/)).not.toBeInTheDocument())
    expect(within(sheet).getByText('Pasuje')).toBeInTheDocument()
  })

  it('błąd zapisu odpowiedzi pokazuje komunikat', async () => {
    routeApi({ 'GET /api/benefits': [MAYBE], 'POST /api/benefits/nat-kdr/answers': new ApiError(422, 'Nieznany warunek.') })
    renderPage()
    await userEvent.click(await screen.findByRole('tab', { name: /sprawdź/i }))
    await userEvent.click(screen.getByRole('button', { name: /karta dużej rodziny/i }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Nie' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Nieznany warunek.')
  })

  it('wyszukiwarka filtruje po nazwie (bez polskich znaków też)', async () => {
    routeApi({ 'GET /api/benefits': [FITS, MAYBE, NO] })
    renderPage()
    await userEvent.click(await screen.findByRole('tab', { name: /wszystkie/i }))
    await userEvent.type(screen.getByLabelText(/szukaj świadczenia/i), 'zyciem')
    const list = screen.getByRole('region', { name: /przeglądaj świadczenia/i })
    expect(within(list).getByRole('button', { name: /za życiem/i })).toBeInTheDocument()
    expect(within(list).queryByRole('button', { name: /800 plus/i })).not.toBeInTheDocument()
  })

  it('pokazuje stawki z etykietą „Parametry ZUS 2026 – aktywne”', async () => {
    routeApi({
      'GET /api/benefits': [FITS],
      'GET /api/parametry': { zasilek_macierzynski_procent: { jednolity_wniosek_21_dni: 81.5 }, becikowe_zl: 1000 },
      'GET /api/summary': { totals: {}, estimated_annual_total: 0, nearest_deadline: null, parameters_label: 'Parametry ZUS 2026 – aktywne' },
    })
    renderPage()
    const rates = await screen.findByRole('region', { name: /stawki/i })
    expect(await within(rates).findByText('81,5%')).toBeInTheDocument()
    expect(within(rates).getByText('Parametry ZUS 2026 – aktywne')).toBeInTheDocument()
  })
})
