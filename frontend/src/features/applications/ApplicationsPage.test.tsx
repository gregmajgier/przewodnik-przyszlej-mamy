import { screen, within } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../lib/api'
import { ANNA, makeSession, renderWithSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import ApplicationsPage from './ApplicationsPage'
import widget from './widget'
import { ANNA_ID, FORMS, makeApp, makeFamily, PIOTR } from './testData'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

const FAMILY = makeFamily(ANNA)

const APPS = [
  makeApp({ id: 'app-1', status: 'needs_input' }),
  makeApp({ id: 'app-2', form_code: 'ZAM', channel: 'portal_agent', applicant_id: PIOTR.id, child_id: 'c-maja', status: 'sent', created_at: '2026-11-20T10:00:00Z' }),
]

function renderList(user = ANNA) {
  return renderWithSession(
    <Routes>
      <Route path="/wnioski" element={<ApplicationsPage />} />
      <Route path="/start" element={<p>Start</p>} />
    </Routes>,
    { route: '/wnioski', session: makeSession({ family: FAMILY, user }) },
  )
}

beforeEach(() => vi.clearAllMocks())

describe('ApplicationsPage', () => {
  it('pokazuje wnioski całej rodziny ze statusem, dzieckiem i informacją, kto składa', async () => {
    routeApi({ 'GET /api/applications': APPS, 'GET /api/applications/forms': FORMS })
    renderList()
    const rows = await screen.findAllByRole('listitem')
    expect(rows).toHaveLength(2)

    const mine = rows[0]
    expect(within(mine).getByRole('link', { name: /urlop macierzyński i rodzicielski/i })).toHaveAttribute('href', '/wnioski/app-1')
    expect(within(mine).getByText('Brakuje danych')).toBeInTheDocument()
    expect(within(mine).getByText(/składa: Ty/)).toBeInTheDocument()
    expect(within(mine).getByText(/dziecko: Dziecko w drodze/)).toBeInTheDocument()
    expect(within(mine).getByRole('link', { name: 'Kontynuuj' })).toBeInTheDocument()

    const partner = rows[1]
    expect(within(partner).getByText('Wysłany')).toBeInTheDocument()
    expect(within(partner).getByText(/składa: Piotr Nowak/)).toBeInTheDocument()
    expect(within(partner).getByRole('link', { name: 'Zobacz' })).toHaveAttribute('href', '/wnioski/app-2')
  })

  it('z punktu widzenia drugiego rodzica „Ty” to on, a Anna jest wymieniona z imienia', async () => {
    routeApi({ 'GET /api/applications': APPS, 'GET /api/applications/forms': FORMS })
    renderList(PIOTR)
    const rows = await screen.findAllByRole('listitem')
    expect(within(rows[0]).getByText(/składa: Anna Nowak/)).toBeInTheDocument()
    expect(within(rows[1]).getByText(/składa: Ty/)).toBeInTheDocument()
    expect(ANNA_ID).toBe('user-nowak-anna')
  })

  it('podpowiada polecaną kolejność z linkami do kreatora', async () => {
    routeApi({ 'GET /api/applications': [], 'GET /api/applications/forms': FORMS })
    renderList()
    const flow = await screen.findByRole('region', { name: /polecana kolejność/i })
    const links = within(flow).getAllByRole('link')
    expect(links.map((l) => l.getAttribute('href'))).toEqual(['/wnioski/nowy?form=URLOP-MAC-ROD', '/wnioski/nowy?form=ZAM'])
    expect(screen.getByText(/nie macie jeszcze żadnych wniosków/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Nowy wniosek' })).toHaveAttribute('href', '/wnioski/nowy')
  })

  it('bez katalogu pokazuje kody wniosków zamiast nazw', async () => {
    routeApi({ 'GET /api/applications': [APPS[0]], 'GET /api/applications/forms': new ApiError(500, 'błąd') })
    renderList()
    expect(await screen.findByRole('link', { name: 'URLOP-MAC-ROD' })).toBeInTheDocument()
  })

  it('błąd listy pokazuje komunikat', async () => {
    routeApi({ 'GET /api/applications': new ApiError(404, 'Nie należysz jeszcze do żadnej rodziny.'), 'GET /api/applications/forms': FORMS })
    renderList()
    expect(await screen.findByRole('alert')).toHaveTextContent('Nie należysz jeszcze do żadnej rodziny.')
  })

  it('bez rodziny przekierowuje na /start', async () => {
    routeApi({})
    renderWithSession(
      <Routes>
        <Route path="/wnioski" element={<ApplicationsPage />} />
        <Route path="/start" element={<p>Start</p>} />
      </Routes>,
      { route: '/wnioski', session: makeSession({ family: null }) },
    )
    expect(await screen.findByText('Start')).toBeInTheDocument()
  })
})

describe('kafelek „Wnioski” na dashboardzie', () => {
  const Widget = widget.Component

  it('pokazuje tylko rozpoczęte wnioski i link do nowego', async () => {
    routeApi({ 'GET /api/applications': APPS, 'GET /api/applications/forms': FORMS })
    renderWithSession(<Widget />, { session: makeSession({ family: FAMILY }) })
    expect(await screen.findByRole('link', { name: /urlop macierzyński i rodzicielski/i })).toHaveAttribute('href', '/wnioski/app-1')
    expect(screen.getByText(/brakuje danych/i)).toBeInTheDocument()
    expect(screen.queryByText(/zasiłek macierzyński$/i)).not.toBeInTheDocument() // wysłany nie jest „w toku”
    expect(screen.getByRole('link', { name: 'Nowy wniosek' })).toBeInTheDocument()
  })

  it('bez rozpoczętych wniosków pokazuje pusty stan', async () => {
    routeApi({ 'GET /api/applications': [APPS[1]], 'GET /api/applications/forms': FORMS })
    renderWithSession(<Widget />, { session: makeSession({ family: FAMILY }) })
    expect(await screen.findByText(/nie masz rozpoczętych wniosków/i)).toBeInTheDocument()
  })

  it('błąd ładowania nie psuje panelu', async () => {
    routeApi({ 'GET /api/applications': new ApiError(500, 'błąd'), 'GET /api/applications/forms': FORMS })
    renderWithSession(<Widget />, { session: makeSession({ family: FAMILY }) })
    expect(await screen.findByText(/nie udało się wczytać wniosków/i)).toBeInTheDocument()
  })
})
