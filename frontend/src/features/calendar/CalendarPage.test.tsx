import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import CalendarPage from './CalendarPage'
import type { CalendarEvent } from './types'

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
  ...base, id: 'e2', kind: 'application', title: 'Wniosek URLOP-OJC',
  summary: 'Złożono: 20.11.2026. Termin zakończenia nie jest znany. Do: kadry@firma.pl. Status: wysłany.',
  due_date: '2026-11-20', date_label: 'Złożono', actor_name: 'Piotr Nowak', recipient: 'kadry@firma.pl', status: 'sent',
  done: true, source_ref: 'application:a',
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
    await userEvent.click(within(card).getByRole('checkbox', { name: 'Zrobione: Zasiłek macierzyński: wniosek' }))
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith('/api/calendar/e1', { method: 'PATCH', body: { done: true } }),
    )
    // zrobione chowają się z „Nadchodzących” i lądują w „Zrobione”
    await waitFor(() => expect(screen.queryByRole('article', { name: 'Zasiłek macierzyński: wniosek' })).not.toBeInTheDocument())
    await userEvent.click(screen.getByRole('tab', { name: /zrobione/i }))
    expect(screen.getByRole('checkbox', { name: 'Zrobione: Zasiłek macierzyński: wniosek' })).toHaveAttribute('aria-checked', 'true')
  })

  it('wniosek: ludzka nazwa zamiast kodu, kto złożył i do kogo', async () => {
    routeApi({ 'GET /api/calendar': [APP] })
    renderWithSession(<CalendarPage />)
    await screen.findByText('Odhaczone wpisy widzi też drugi rodzic.')
    expect(screen.queryByRole('article', { name: 'Urlop ojcowski' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('tab', { name: /zrobione/i }))
    const card = await screen.findByRole('article', { name: 'Urlop ojcowski' })
    expect(within(card).getByText(/^złożono /i)).toBeInTheDocument()
    expect(within(card).getByText(/termin zakończenia nie jest znany/i)).toBeInTheDocument()
    expect(within(card).queryByRole('checkbox')).not.toBeInTheDocument()
    expect(within(card).getByText('Piotr Nowak')).toBeInTheDocument()
    expect(within(card).getByText('kadry@firma.pl')).toBeInTheDocument()
  })

  it('filtr „zagrożone” pokazuje ostrzeżenia i terminy po czasie', async () => {
    routeApi({ 'GET /api/calendar': [base, RISK, { ...base, id: 'e4', title: 'Stary termin', overdue: true }] })
    renderWithSession(<CalendarPage />)
    await screen.findByText('Brak zasiłku przy zleceniu')
    await userEvent.click(screen.getByRole('tab', { name: /pilne/i }))
    expect(screen.getByText('Brak zasiłku przy zleceniu')).toBeInTheDocument()
    expect(screen.getByText('Stary termin')).toBeInTheDocument()
    expect(screen.getByText('Po terminie')).toBeInTheDocument()
    expect(screen.queryByRole('article', { name: 'Zasiłek macierzyński: wniosek' })).not.toBeInTheDocument()
  })

  it('pusta lista: przyjazny komunikat zamiast pustki', async () => {
    routeApi({ 'GET /api/calendar': [] })
    renderWithSession(<CalendarPage />)
    expect(await screen.findByText(/Wszystko odhaczone/)).toBeInTheDocument()
  })

  it('siatka miesiąca: dzień z wpisem przewija do niego, nawet gdy jest w innej zakładce', async () => {
    const done = { ...base, id: 'e9', title: 'Zrobiony wpis', due_date: '2026-12-10', done: true }
    routeApi({ 'GET /api/calendar': [base, done] })
    renderWithSession(<CalendarPage />)
    await screen.findByRole('article', { name: 'Zasiłek macierzyński: wniosek' })
    // przejście do grudnia 2026 strzałkami, niezależnie od dzisiejszej daty
    const MONTHS = ['Styczeń', 'Luty', 'Marzec', 'Kwiecień', 'Maj', 'Czerwiec', 'Lipiec', 'Sierpień', 'Wrzesień', 'Październik', 'Listopad', 'Grudzień']
    const shown = () => {
      const [m, y] = (screen.getByRole('grid').getAttribute('aria-label') ?? '').split(' ')
      return Number(y) * 12 + MONTHS.indexOf(m)
    }
    const target = 2026 * 12 + 11
    while (shown() !== target) {
      await userEvent.click(screen.getByRole('button', { name: shown() < target ? 'Następny miesiąc' : 'Poprzedni miesiąc' }))
    }
    await userEvent.click(screen.getByRole('button', { name: /10 grudnia: 1 wpis/ }))
    expect(screen.getByRole('tab', { name: /zrobione/i })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('article', { name: 'Zrobiony wpis' })).toBeInTheDocument()
  })

})
