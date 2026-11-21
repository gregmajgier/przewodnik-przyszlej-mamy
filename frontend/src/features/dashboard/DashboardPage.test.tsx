import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { FamilyView } from '../../lib/types'
import { ANNA, makeSession, renderWithSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import type { Summary } from '../benefits/types'
import DashboardPage from './DashboardPage'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))
vi.mock('./widgets', () => ({
  dashboardWidgets: [
    { order: 2, Component: () => <p>Widget drugi</p> },
    { order: 1, Component: () => <p>Widget pierwszy</p> },
  ],
}))

const FAMILY = {
  family: { id: 'f1', name: 'Rodzina Nowak', owner_id: ANNA.id, member_ids: [ANNA.id], invite_code: null, invite_expires_at: null },
  members: [ANNA],
  children: [],
  pending_requests: [],
} as FamilyView

const SUMMARY: Summary = {
  family_name: 'Rodzina Nowak',
  totals: { national: 22, local: 0, fits: 7, maybe: 3, no: 12 },
  estimated_annual_total: 21424,
  nearest_deadline: { benefit_id: 'nat-dobry-start', name: 'Dobry Start', date: '2026-11-30', days_left: 9 },
  warnings: ['Dobry Start: termin 30.11.2026'],
  parameters_label: 'Parametry ZUS 2026 – aktywne',
}

const PARAMS = {
  zasilek_macierzynski_procent: { macierzynski: 100, rodzicielski: 70, jednolity_wniosek_21_dni: 81.5 },
  swiadczenie_rodzicielskie_zl_mies: 1000,
  becikowe_zl: 1000,
  za_zyciem_zl: 4000,
}

function renderDash(session = makeSession({ family: FAMILY })) {
  return renderWithSession(
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/start" element={<p>Zaczynamy</p>} />
    </Routes>,
    { session },
  )
}

describe('DashboardPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('nagłówek: liczba świadczeń, kwota roczna, najbliższy termin, etykieta parametrów', async () => {
    routeApi({ 'GET /api/summary': SUMMARY, 'GET /api/parametry': PARAMS })
    renderDash()
    expect(await screen.findByText('10')).toBeInTheDocument() // 7 pasuje + 3 może
    expect(screen.getByText(/7 pasuje/)).toBeInTheDocument()
    expect(screen.getByText(/21\s424\s*zł/)).toBeInTheDocument()
    expect(screen.getByText('Dobry Start')).toBeInTheDocument()
    expect(screen.getByText(/30\.11\.2026 · za 9 dni/)).toBeInTheDocument()
    expect(screen.getByText('Parametry ZUS 2026 – aktywne')).toBeInTheDocument()
  })

  it('stawki z /api/parametry', async () => {
    routeApi({ 'GET /api/summary': SUMMARY, 'GET /api/parametry': PARAMS })
    renderDash()
    expect(await screen.findByText(/Becikowe/)).toBeInTheDocument()
    expect(screen.getByText(/4\s000\s*zł/)).toBeInTheDocument()
    expect(screen.getByText(/81,5/)).toBeInTheDocument()
  })

  it('ostrzeżenia z podsumowania', async () => {
    routeApi({ 'GET /api/summary': SUMMARY, 'GET /api/parametry': PARAMS })
    renderDash()
    expect(await screen.findByText(/Dobry Start: termin 30\.11\.2026/)).toBeInTheDocument()
  })

  it('widgety posortowane po order', async () => {
    routeApi({ 'GET /api/summary': SUMMARY, 'GET /api/parametry': PARAMS })
    renderDash()
    const first = await screen.findByText('Widget pierwszy')
    const second = screen.getByText('Widget drugi')
    expect(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('bez rodziny przekierowuje do /start', () => {
    routeApi({})
    renderDash(makeSession({ family: null }))
    expect(screen.getByText('Zaczynamy')).toBeInTheDocument()
  })

  it('awaria parametrów nie psuje panelu', async () => {
    routeApi({ 'GET /api/summary': SUMMARY })
    renderDash()
    expect(await screen.findByText('Widget pierwszy')).toBeInTheDocument()
    expect(screen.getByText('Parametry ZUS 2026 – aktywne')).toBeInTheDocument()
  })
})
