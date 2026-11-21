import { screen, within } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../lib/api'
import type { FamilyView, User } from '../../lib/types'
import { ANNA, makeSession, renderWithSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import type { Summary } from '../benefits/types'
import DashboardPage from './DashboardPage'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

// Widgety rejestru (benefits, applications) mają własne testy — tu sprawdzamy tylko, że dashboard je osadza.
vi.mock('./widgets', () => ({
  getDashboardWidgets: () => [
    { order: 1, Component: () => <section aria-label="Kafelek A">A</section> },
    { order: 2, Component: () => <section aria-label="Kafelek B">B</section> },
  ],
}))

const FAMILY = {
  family: { id: 'f1', name: 'Nowak', owner_id: ANNA.id, member_ids: [ANNA.id], invite_code: null, invite_expires_at: null },
  members: [ANNA],
  children: [],
  pending_requests: [],
} as FamilyView

const SUMMARY: Summary = {
  totals: { national: 20, local: 2, fits: 7, maybe: 5, no: 10 },
  estimated_annual_total: 12000,
  nearest_deadline: { date: '2027-01-15', benefit_id: 'nat-bec', benefit_name: 'Becikowe' },
  parameters_label: 'Parametry ZUS 2026 – aktywne',
}

const PARAMS = {
  zasilek_macierzynski_procent: { macierzynski: 100, rodzicielski: 70, jednolity_wniosek_21_dni: 81.5 },
  swiadczenie_rodzicielskie_zl_mies: 1000,
  becikowe_zl: 1000,
  za_zyciem_zl: 4000,
}

function Tree() {
  return (
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/start" element={<p>Start</p>} />
      <Route path="/urzednik" element={<p>Panel urzędnika</p>} />
    </Routes>
  )
}

const flat = (el: HTMLElement) => (el.textContent ?? '').replace(/ /g, ' ')

describe('DashboardPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('pokazuje podsumowanie z API: liczbę świadczeń, kwotę roczną i najbliższy termin', async () => {
    routeApi({ 'GET /api/summary': SUMMARY, 'GET /api/parametry': PARAMS })
    renderWithSession(<Tree />, { session: makeSession({ family: FAMILY }) })

    expect(await screen.findByRole('heading', { name: /cześć, anna/i })).toBeInTheDocument()
    const summary = await screen.findByLabelText('Podsumowanie')
    const text = flat(summary)
    expect(text).toMatch(/12\s?000\s?zł/)
    expect(text).toContain('15.01.2027')
    expect(text).toContain('Becikowe')
    expect(within(summary).getByText('12')).toBeInTheDocument() // 7 pasuje + 5 może = 12 świadczeń
  })

  it('pokazuje stawki z /api/parametry z etykietą „Parametry ZUS 2026 – aktywne”', async () => {
    routeApi({ 'GET /api/summary': SUMMARY, 'GET /api/parametry': PARAMS })
    renderWithSession(<Tree />, { session: makeSession({ family: FAMILY }) })

    const rates = await screen.findByRole('region', { name: /stawki/i })
    expect(within(rates).getByText('Parametry ZUS 2026 – aktywne')).toBeInTheDocument()
    expect(await within(rates).findByText('81,5%')).toBeInTheDocument()
    expect(within(rates).getByText('70%')).toBeInTheDocument()
    expect(flat(rates)).toMatch(/Świadczenie rodzicielskie\s*1\s?000\s?zł \/ mies\./)
    expect(flat(rates)).toMatch(/„Za życiem”\s*4\s?000\s?zł/)
  })

  it('brak nadchodzącego terminu — „brak”', async () => {
    routeApi({ 'GET /api/summary': { ...SUMMARY, nearest_deadline: null }, 'GET /api/parametry': PARAMS })
    renderWithSession(<Tree />, { session: makeSession({ family: FAMILY }) })
    expect(await screen.findByText('brak')).toBeInTheDocument()
  })

  it('osadza widgety z rejestru', async () => {
    routeApi({ 'GET /api/summary': SUMMARY, 'GET /api/parametry': PARAMS })
    renderWithSession(<Tree />, { session: makeSession({ family: FAMILY }) })
    await screen.findByRole('heading', { name: /cześć/i })
    expect(await screen.findByLabelText('Kafelek A')).toBeInTheDocument()
    expect(screen.getByLabelText('Kafelek B')).toBeInTheDocument()
  })

  it('panel działa, gdy stawki się nie wczytają', async () => {
    routeApi({ 'GET /api/summary': SUMMARY, 'GET /api/parametry': new ApiError(500, 'błąd') })
    renderWithSession(<Tree />, { session: makeSession({ family: FAMILY }) })
    expect(await screen.findByText('Becikowe')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByText('Parametry ZUS 2026 – aktywne')).toBeInTheDocument() // etykieta zostaje
  })

  it('błąd podsumowania pokazuje komunikat', async () => {
    routeApi({ 'GET /api/summary': new ApiError(404, 'Nie znaleziono profilu.'), 'GET /api/parametry': PARAMS })
    renderWithSession(<Tree />, { session: makeSession({ family: FAMILY }) })
    expect(await screen.findByRole('alert')).toHaveTextContent('Nie znaleziono profilu.')
  })

  it('bez rodziny przekierowuje na /start, urzędnika na panel urzędnika', async () => {
    routeApi({})
    const { unmount } = renderWithSession(<Tree />, { session: makeSession({ family: null }) })
    expect(await screen.findByText('Start')).toBeInTheDocument()
    unmount()
    const official: User = { ...ANNA, role: 'official', name: 'Urzędnik' }
    renderWithSession(<Tree />, { session: makeSession({ user: official }) })
    expect(await screen.findByText('Panel urzędnika')).toBeInTheDocument()
  })
})
