import { screen, waitFor, within } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../lib/api'
import { NOWAK } from '../../test/fixtures'
import { ANNA, makeSession, renderWithSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import { FORMS, makeApp } from '../applications/testData'
import type { BenefitMatch, Summary } from '../benefits/types'
import DashboardPage from './DashboardPage'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

const SUMMARY: Summary = {
  totals: { national: 20, local: 2, fits: 7, maybe: 5, no: 10 },
  estimated_annual_total: 12000,
  nearest_deadline: { date: '2027-01-15', benefit_id: 'nat-becikowe', benefit_name: 'Becikowe' },
  parameters_label: 'Parametry ZUS 2026 – aktywne',
}

function benefit(id: string, name: string, status: 'fits' | 'maybe' | 'no'): BenefitMatch {
  return {
    benefit: {
      id, name, scope: 'national', unit_id: null, category: 'benefit', description: '', amount_text: null,
      annual_value_estimate: null, how_to_apply: '', form_codes: [], source_url: 'https://example.gov.pl', extra_text: null, verify: false,
    },
    match: { status, reasons: [], unmet: [], questions: [] },
  }
}

const BENEFITS = [
  benefit('nat-zasilek-macierzynski', 'Zasiłek macierzyński', 'fits'),
  benefit('nat-urlop-rodzicielski', 'Urlop rodzicielski', 'fits'),
  benefit('nat-becikowe', 'Becikowe', 'maybe'),
  benefit('nat-800-plus', 'Świadczenie wychowawcze 800+', 'fits'),
  benefit('nat-dobry-start', 'Dobry Start (300+)', 'fits'),
  benefit('nat-kdr', 'Karta Dużej Rodziny', 'no'),
]

const APPS = [makeApp({ id: 'app-1', status: 'needs_input', child_id: 'c-unborn' })]

function routes(over: Record<string, unknown> = {}) {
  return routeApi({
    'GET /api/summary': SUMMARY,
    'GET /api/benefits': BENEFITS,
    'GET /api/calendar': [
      { id: 'e1', kind: 'deadline', title: 'Wniosek URLOP-MAC-ROD', summary: '', due_date: '2026-12-01', done: false, overdue: false, muted: false },
    ],
    'GET /api/applications': APPS,
    'GET /api/applications/forms': FORMS,
    'GET /api/mail/threads': [],
    'POST /api/mail/sync': { new_messages: 0 },
    ...over,
  })
}

function Tree() {
  return (
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/start" element={<p>Start</p>} />
    </Routes>
  )
}

const flat = (el: HTMLElement) => (el.textContent ?? '').replace(/ /g, ' ')

describe('DashboardPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('hero: powitanie, liczba świadczeń dla rodziny, najbliższy termin i kwota roczna', async () => {
    routes()
    renderWithSession(<Tree />, { session: makeSession({ family: NOWAK }) })
    const hero = await screen.findByRole('region', { name: /anna/i })
    await waitFor(() => expect(flat(hero)).toContain('5 świadczeń')) // 4 pasuje + 1 może; „nie pasuje” nie liczymy
    expect(flat(hero)).toContain('Becikowe')
    expect(flat(hero)).toContain('15.01.2027')
    expect(flat(hero)).toMatch(/12\s?000\s?zł/)
  })

  it('kafelki spraw: cała rodzina, zalogowany rodzic i każde dziecko — bez spraw drugiego rodzica', async () => {
    routes()
    renderWithSession(<Tree />, { session: makeSession({ family: NOWAK }) })
    const people = await screen.findByRole('region', { name: /wasze sprawy/i })
    const links = within(people).getAllByRole('link').filter((a) => a.getAttribute('href')?.startsWith('/sprawy/'))
    expect(links.map((a) => a.getAttribute('href'))).toEqual(['/sprawy/rodzina', `/sprawy/${ANNA.id}`, '/sprawy/c-maja', '/sprawy/c-antek', '/sprawy/c-unborn'])
    await waitFor(() => expect(within(links[1]).getByText('2 sprawy')).toBeInTheDocument()) // urlopy i zasiłek rodzica
    expect(within(links[0]).getByText(/1 sprawa/)).toBeInTheDocument() // 800+ to sprawa całej rodziny
    expect(within(links[4]).getByText('Maleństwo')).toBeInTheDocument() // dziecko w drodze
    expect(within(links[4]).getByText('1 sprawa')).toBeInTheDocument() // becikowe
  })

  it('skróty prowadzą do ekranów i pokazują kluczowe informacje (wnioski, baza świadczeń, kalendarz)', async () => {
    routes()
    renderWithSession(<Tree />, { session: makeSession({ family: NOWAK }) })
    const apps = await screen.findByRole('link', { name: /wnioski/i })
    expect(apps).toHaveAttribute('href', '/wnioski')
    expect(await within(apps).findByText('Urlop macierzyński i rodzicielski')).toBeInTheDocument()
    expect(within(apps).getByText('Brakuje danych')).toBeInTheDocument()
    const base = screen.getByRole('link', { name: /baza świadczeń/i })
    expect(base).toHaveAttribute('href', '/swiadczenia')
    const top = await within(base).findByRole('list', { name: /najwięcej dla was/i })
    expect(within(top).getAllByRole('listitem')).toHaveLength(3) // kafelek pokazuje konkretne świadczenia, nie same liczby
    expect(flat(base)).toContain('4 pasuje')
    expect(flat(base)).toContain('1 do sprawdzenia')
    const cal = screen.getByRole('link', { name: /kalendarz/i })
    expect(await within(cal).findByText('Urlop macierzyński i rodzicielski')).toBeInTheDocument() // kod wniosku → nazwa
    expect(screen.getAllByRole('link', { name: /^rodzina/i }).every((a) => a.getAttribute('href') === '/rodzina')).toBe(true)
  })

  it('przy wejściu sprawdza pocztę, żeby statusy wniosków były aktualne', async () => {
    const mocked = routes()
    renderWithSession(<Tree />, { session: makeSession({ family: NOWAK }) })
    await waitFor(() => expect(mocked).toHaveBeenCalledWith('/api/mail/sync', { method: 'POST' }))
  })

  it('błąd podsumowania pokazuje komunikat, a reszta panelu działa', async () => {
    routes({ 'GET /api/summary': new ApiError(404, 'Nie znaleziono profilu.') })
    renderWithSession(<Tree />, { session: makeSession({ family: NOWAK }) })
    expect(await screen.findByRole('alert')).toHaveTextContent('Nie znaleziono profilu.')
    expect(screen.getByRole('region', { name: /wasze sprawy/i })).toBeInTheDocument()
  })

  it('bez rodziny przekierowuje na /start', async () => {
    routes()
    renderWithSession(<Tree />, { session: makeSession({ family: null }) })
    expect(await screen.findByText('Start')).toBeInTheDocument()
  })
})
