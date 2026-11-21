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

  it('grupuje świadczenia: pasuje, może, a niepasujące chowa za „Pokaż pozostałe”', async () => {
    routeApi({ 'GET /api/benefits': [FITS, MAYBE, NO] })
    renderPage()

    const fits = await screen.findByRole('region', { name: /^pasuje/i })
    expect(within(fits).getByRole('heading', { name: '800 plus' })).toBeInTheDocument()
    expect(within(fits).getByText(/dziecko ma 3 lata i mieszkasz w Krakowie/)).toBeInTheDocument()
    expect(within(fits).getByText('800 zł miesięcznie')).toBeInTheDocument()

    const maybe = screen.getByRole('region', { name: /może ci przysługiwać/i })
    expect(within(maybe).getByRole('heading', { name: 'Karta Dużej Rodziny' })).toBeInTheDocument()

    const summary = screen.getByText(/pokaż pozostałe \(1\)/i)
    expect(summary.closest('details')).not.toHaveAttribute('open')
  })

  it('niepasujące pokazują powód („dlaczego nie”)', async () => {
    routeApi({ 'GET /api/benefits': [NO] })
    renderPage()
    await screen.findByText(/pokaż pozostałe/i)
    await userEvent.click(screen.getByText(/pokaż pozostałe/i))
    expect(screen.getByText(/dlaczego nie/i)).toBeInTheDocument()
    expect(screen.getByText(/nie ma orzeczenia o niepełnosprawności/)).toBeInTheDocument()
    expect(screen.getByText(/dane do weryfikacji/i)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /złóż wniosek/i })).not.toBeInTheDocument() // „no” bez wniosku
  })

  it('„Złóż wniosek” prowadzi do kreatora z kodem formularza, link do źródła w nowej karcie', async () => {
    routeApi({ 'GET /api/benefits': [FITS] })
    renderPage()
    const apply = await screen.findByRole('link', { name: /złóż wniosek/i })
    expect(apply).toHaveAttribute('href', '/wnioski/nowy?form=800PLUS')
    const source = screen.getByRole('link', { name: /źródło/i })
    expect(source).toHaveAttribute('href', 'https://www.gov.pl/zrodlo')
    expect(source).toHaveAttribute('target', '_blank')
    expect(source).toHaveAttribute('rel', expect.stringContaining('noopener'))
    await userEvent.click(apply)
    expect(await screen.findByText('Kreator wniosku')).toBeInTheDocument()
  })

  it('brak form_codes = brak przycisku „Złóż wniosek”', async () => {
    routeApi({ 'GET /api/benefits': [{ ...FITS, benefit: { ...FITS.benefit, form_codes: [] } }] })
    renderPage()
    await screen.findByRole('heading', { name: '800 plus' })
    expect(screen.queryByRole('link', { name: /złóż wniosek/i })).not.toBeInTheDocument()
  })

  it('odpowiedź tak/nie zapisuje się przez API i przelicza dopasowanie', async () => {
    const fitsNow: BenefitMatch = { ...MAYBE, match: { status: 'fits', reasons: ['dochód poniżej progu'], unmet: [], questions: [] } }
    const mocked = routeApi({
      'GET /api/benefits': [MAYBE],
      'POST /api/benefits/nat-kdr/answers': fitsNow,
    })
    renderPage()
    await screen.findByText(/czy dochód na osobę/i)
    await userEvent.click(screen.getByRole('button', { name: 'Tak' }))
    await waitFor(() =>
      expect(mocked).toHaveBeenCalledWith('/api/benefits/nat-kdr/answers', {
        method: 'POST',
        body: { condition_id: 'income', answer: true },
      }),
    )
    // karta przeszła do grupy „Pasuje” i pytanie zniknęło
    const fits = await screen.findByRole('region', { name: /^pasuje \(1\)/i })
    expect(within(fits).getByText('dochód poniżej progu')).toBeInTheDocument()
    expect(screen.queryByText(/czy dochód na osobę/i)).not.toBeInTheDocument()
  })

  it('błąd zapisu odpowiedzi pokazuje komunikat i zostawia pytanie', async () => {
    routeApi({
      'GET /api/benefits': [MAYBE],
      'POST /api/benefits/nat-kdr/answers': new ApiError(422, 'To świadczenie nie ma takiego pytania.'),
    })
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Nie' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('To świadczenie nie ma takiego pytania.')
    expect(screen.getByText(/czy dochód na osobę/i)).toBeInTheDocument()
  })

  it('błąd ładowania listy pokazuje komunikat', async () => {
    routeApi({ 'GET /api/benefits': new ApiError(500, 'Coś poszło nie tak po naszej stronie.') })
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent('Coś poszło nie tak po naszej stronie.')
  })

  it('bez rodziny przekierowuje na /start', async () => {
    routeApi({})
    renderPage(null)
    expect(await screen.findByText('Start')).toBeInTheDocument()
  })

  describe('zwarta lista', () => {
    const FORMS_CATALOG = {
      recommended_flow: [],
      forms: [
        { code: 'URLOP-MAC-ROD', name: 'Urlop', institution: 'pracodawca', deadline: null, channels: ['employer_email'], default_channel: 'employer_email', only_electronic: false, requires_child: true, portal_id: null },
        { code: 'ZAM', name: 'ZAM', institution: 'ZUS lub płatnik', deadline: null, channels: ['portal_agent'], default_channel: 'portal_agent', only_electronic: false, requires_child: true, portal_id: 'ezus_zam' },
      ],
    }
    const maternity: BenefitMatch = {
      benefit: benefit({ id: 'nat-mac', name: 'Urlop i zasiłek macierzyński', amount_text: '100% podstawy', form_codes: ['URLOP-MAC-ROD', 'ZAM'], annual_value_estimate: 30000, description: 'Płatny urlop po porodzie.', how_to_apply: 'Złóż wniosek u pracodawcy.' }),
      match: { status: 'fits', reasons: ['w rodzinie jest dziecko w drodze (ciąża)', 'masz umowę o pracę'], unmet: [], questions: [] },
    }

    it('przyciski mówią, do kogo trafia wniosek, a nie pokazują kodów formularzy', async () => {
      routeApi({ 'GET /api/benefits': [maternity], 'GET /api/applications/forms': FORMS_CATALOG })
      renderPage()
      const employer = await screen.findByRole('link', { name: 'Wniosek dla pracodawcy' })
      expect(employer).toHaveAttribute('href', '/wnioski/nowy?form=URLOP-MAC-ROD')
      expect(screen.getByRole('link', { name: 'Wniosek do ZUS' })).toHaveAttribute('href', '/wnioski/nowy?form=ZAM')
      expect(screen.queryByText(/URLOP-MAC-ROD|\(ZAM\)/)).not.toBeInTheDocument()
      expect(screen.getByText('Wymaga złożenia wniosku')).toBeInTheDocument()
    })

    it('opis, sposób złożenia i pełna lista powodów są w zwijanych „Szczegółach”', async () => {
      routeApi({ 'GET /api/benefits': [maternity] })
      renderPage()
      const summary = await screen.findByText('Szczegóły')
      const details = summary.closest('details') as HTMLElement
      expect(details).not.toHaveAttribute('open')
      expect(within(details).getByText('Płatny urlop po porodzie.')).toBeInTheDocument()
      expect(within(details).getByText(/jak skorzystać/i)).toBeInTheDocument()
      await userEvent.click(summary)
      expect(details).toHaveAttribute('open')
    })

    it('uwaga „do weryfikacji” jest raz na stronie, a nie w każdej karcie', async () => {
      const verify = (id: string) => ({ ...FITS, benefit: { ...FITS.benefit, id, name: id, verify: true } })
      routeApi({ 'GET /api/benefits': [verify('a'), verify('b'), verify('c')] })
      renderPage()
      await screen.findByRole('heading', { name: 'a' })
      expect(document.querySelectorAll('.benefits-verify-note')).toHaveLength(1)
      expect(screen.getAllByText(/dane do weryfikacji, sprawdź je w źródle/i)).toHaveLength(3) // tylko w zwiniętych szczegółach
    })

    it('powód wspólny dla większości kart pokazujemy raz nad listą, nie w każdej karcie', async () => {
      const card = (id: string) => ({
        benefit: benefit({ id, name: `Świadczenie ${id}` }),
        match: { status: 'fits' as const, reasons: ['w rodzinie jest dziecko w drodze (ciąża)'], unmet: [], questions: [] },
      })
      routeApi({ 'GET /api/benefits': [card('a'), card('b'), card('c')] })
      renderPage()
      await screen.findByRole('heading', { name: 'Świadczenie a' })
      expect(screen.getAllByText(/dziecko w drodze \(ciąża\)/)).toHaveLength(1)
      expect(screen.getByText(/dlaczego pasują: w rodzinie jest dziecko w drodze/i)).toBeInTheDocument()
    })

    it('sortowanie po kwocie rocznej ustawia najdroższe świadczenie pierwsze', async () => {
      const cheap: BenefitMatch = { ...FITS, benefit: { ...FITS.benefit, id: 'cheap', name: 'Tanie', annual_value_estimate: 1000 } }
      const rich: BenefitMatch = { ...FITS, benefit: { ...FITS.benefit, id: 'rich', name: 'Drogie', annual_value_estimate: 30000 } }
      routeApi({ 'GET /api/benefits': [cheap, rich] })
      renderPage()
      await screen.findByRole('heading', { name: 'Tanie' })
      const order = () => screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)
      expect(order()).toEqual(['Tanie', 'Drogie'])
      await userEvent.selectOptions(screen.getByLabelText('Sortuj'), 'amount')
      expect(order()).toEqual(['Drogie', 'Tanie'])
    })
  })
})
