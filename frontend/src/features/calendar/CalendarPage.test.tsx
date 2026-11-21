import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import CalendarPage from './CalendarPage'
import type { CalendarEvent } from './types'
import widget from './widget'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

const base: CalendarEvent = {
  id: 'e1', family_id: 'f', kind: 'deadline', title: 'Zasiłek macierzyński: wniosek', summary: 'Złóż wniosek u pracodawcy.',
  due_date: '2026-12-30', effect_until: null, done: false, overdue: false, source_ref: 'benefit:zas', child_id: 'c',
  actor_user_id: null, actor_name: null, recipient: null, status: null, severity: null,
}
const APP: CalendarEvent = {
  ...base, id: 'e2', kind: 'application', title: 'Wniosek URLOP-OJC', summary: 'Złożył: Piotr Nowak.',
  due_date: '2026-11-20', actor_name: 'Piotr Nowak', recipient: 'kadry@firma.pl', status: 'sent', source_ref: 'application:a',
}
const RISK: CalendarEvent = {
  ...base, id: 'e3', kind: 'warning', title: 'Brak zasiłku przy zleceniu', summary: 'Zgłoś się do ZUS.',
  severity: 'high', source_ref: 'risk:r',
}

describe('Kalendarz', () => {
  beforeEach(() => vi.clearAllMocks())

  it('odklikanie wpisu wywołuje PATCH', async () => {
    const api = routeApi({
      'GET /api/calendar': [base, APP],
      'PATCH /api/calendar/e1': { ...base, done: true },
    })
    renderWithSession(<CalendarPage />)
    const card = await screen.findByRole('article', { name: 'Zasiłek macierzyński: wniosek' })
    await userEvent.click(card.querySelector('input[type="checkbox"]') as HTMLInputElement)
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith('/api/calendar/e1', { method: 'PATCH', body: { done: true } }),
    )
    // zrobione chowają się domyślnie
    await waitFor(() => expect(screen.queryByRole('article', { name: 'Zasiłek macierzyński: wniosek' })).not.toBeInTheDocument())
  })

  it('pokazuje kto złożył wniosek i do kogo', async () => {
    routeApi({ 'GET /api/calendar': [APP] })
    renderWithSession(<CalendarPage />)
    expect(await screen.findByText(/Kto: Piotr Nowak/)).toBeInTheDocument()
    expect(screen.getByText(/Do: kadry@firma.pl/)).toBeInTheDocument()
  })

  it('filtr „zagrożone” pokazuje ostrzeżenia i terminy po czasie', async () => {
    routeApi({ 'GET /api/calendar': [base, RISK, { ...base, id: 'e4', title: 'Stary termin', overdue: true }] })
    renderWithSession(<CalendarPage />)
    await screen.findByText('Brak zasiłku przy zleceniu')
    await userEvent.click(screen.getByLabelText(/Tylko zagrożone/))
    expect(screen.getByText('Brak zasiłku przy zleceniu')).toBeInTheDocument()
    expect(screen.getByText('Stary termin')).toBeInTheDocument()
    expect(screen.getByText('po terminie')).toBeInTheDocument()
    expect(screen.queryByText('Zasiłek macierzyński: wniosek')).not.toBeInTheDocument()
  })

  it('wspomina o przyszłych przypomnieniach mailem i SMS-em', async () => {
    routeApi({ 'GET /api/calendar': [] })
    renderWithSession(<CalendarPage />)
    expect(await screen.findByText(/Wkrótce: przypomnienia mailem i SMS-em/)).toBeInTheDocument()
  })

  it('widget „Najbliższe terminy” ma order 10 i stawia ostrzeżenia na górze', async () => {
    routeApi({ 'GET /api/calendar': [base, RISK] })
    renderWithSession(<widget.Component />)
    const cards = await screen.findAllByRole('article')
    expect(cards[0]).toHaveAccessibleName('Brak zasiłku przy zleceniu')
    expect(widget.order).toBe(10)
  })
})
