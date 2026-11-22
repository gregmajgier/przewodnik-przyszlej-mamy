import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../lib/api'
import { ANNA, makeSession, renderWithSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import ApplicationsPage from './ApplicationsPage'
import type { MailThread } from './mailTypes'
import { ANNA_ID, FORMS, makeApp, makeFamily, PIOTR } from './testData'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

const FAMILY = makeFamily(ANNA)

const APPS = [
  makeApp({ id: 'app-1', status: 'needs_input' }),
  makeApp({ id: 'app-2', form_code: 'ZAM', channel: 'portal_agent', applicant_id: PIOTR.id, child_id: 'c-maja', status: 'received', sent_at: '2026-11-20T10:00:00Z' }),
  makeApp({ id: 'app-3', form_code: '800PLUS', channel: 'portal_agent', child_id: 'c-maja', status: 'accepted', sent_at: '2026-11-01T10:00:00Z' }),
]

const THREADS: MailThread[] = [
  {
    application: { id: 'app-2', form_code: 'ZAM', status: 'received', applicant_id: PIOTR.id, applicant_name: 'Piotr Nowak', recipient_email: 'wnioski@zus.pl', sent_at: '2026-11-20T10:00:00Z' },
    needs_review: false,
    messages: [
      {
        id: 'm1', folder: 'inbox', from_addr: 'zasilki@zus.pl', to_addr: '', subject: 'Potwierdzenie', body: '…', received_at: '2026-11-21T09:00:00Z',
        classification_status: 'received', classification_confidence: 0.9, classification_summary: 'ZUS potwierdził przyjęcie wniosku.', needs_review: false,
      },
    ],
  },
]

function routes(over: Record<string, unknown> = {}) {
  return routeApi({
    'GET /api/applications': APPS,
    'GET /api/applications/forms': FORMS,
    'GET /api/mail/threads': THREADS,
    'POST /api/mail/sync': { new_messages: 0, status_changes: 0 },
    ...over,
  })
}

function renderList(user = ANNA) {
  return renderWithSession(<ApplicationsPage />, { route: '/wnioski', session: makeSession({ family: FAMILY, user }) })
}

beforeEach(() => vi.clearAllMocks())

describe('ApplicationsPage', () => {
  it('przykładowy wniosek (demo) jest widoczny z etykietą „Przykład”, ale nie da się go otworzyć', async () => {
    routes({ 'GET /api/applications': [makeApp({ id: 'app-demo', status: 'needs_input', demo: true }), APPS[1]] })
    renderList()
    const demo = await screen.findByRole('article', { name: /przykładowy wniosek/i })
    expect(within(demo).getByText('Przykład')).toBeInTheDocument()
    expect(within(demo).getByText(/tylko do podglądu/i)).toBeInTheDocument()
    expect(within(demo).queryByText(/dokończ i podpisz/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /przykład/i })).not.toBeInTheDocument()
    expect(document.querySelector('a[href="/wnioski/app-demo"]')).toBeNull()
    expect(document.querySelector('a[href="/wnioski/app-2"]')).not.toBeNull() // zwykłe wnioski dalej są linkami
  })

  it('„W toku”: krótki tytuł, status, kto składa, którego dziecka dotyczy; zakończone w osobnej zakładce', async () => {
    routes()
    renderList()
    const cards = await screen.findAllByRole('link', { name: /urlop|zasiłek|800/i })
    expect(cards).toHaveLength(2)
    const mine = cards[0]
    expect(mine).toHaveAttribute('href', '/wnioski/app-1')
    expect(within(mine).getByRole('heading', { name: 'Urlop macierzyński i rodzicielski' })).toBeInTheDocument()
    expect(within(mine).getByText('Brakuje danych')).toBeInTheDocument()
    expect(within(mine).getByText('Ty')).toBeInTheDocument()
    expect(within(mine).getByText(/dot\. Maleństwo/)).toBeInTheDocument()
    expect(within(mine).getByText(/dokończ i podpisz/i)).toBeInTheDocument()

    expect(within(cards[1]).getByText('Piotr')).toBeInTheDocument()
    expect(within(cards[1]).getAllByText('Odebrany').length).toBeGreaterThan(0) // pigułka statusu i etap na osi

    await userEvent.click(screen.getByRole('tab', { name: /zakończone/i }))
    expect(await screen.findByRole('link', { name: /świadczenie 800\+/i })).toHaveAttribute('href', '/wnioski/app-3')
  })

  it('pokazuje ostatnią odpowiedź z Gmaila (podsumowanie asystenta) przy wniosku', async () => {
    routes()
    renderList()
    const card = await screen.findByRole('link', { name: /zasiłek macierzyński/i })
    expect(within(card).getByText('ZUS')).toBeInTheDocument()
    expect(within(card).getByText('ZUS potwierdził przyjęcie wniosku.')).toBeInTheDocument()
  })

  it('przy wejściu synchronizuje pocztę, a przycisk pozwala sprawdzić ją ponownie', async () => {
    const mocked = routes()
    renderList()
    await waitFor(() => expect(mocked).toHaveBeenCalledWith('/api/mail/sync', { method: 'POST' }))
    await screen.findByText(/zsynchronizowano/i)
    await userEvent.click(screen.getByRole('button', { name: /sprawdź pocztę teraz/i }))
    await waitFor(() => expect(mocked.mock.calls.filter(([p]) => p === '/api/mail/sync')).toHaveLength(2))
  })

  it('z punktu widzenia drugiego rodzica „Ty” to on', async () => {
    routes()
    renderList(PIOTR)
    const cards = await screen.findAllByRole('link', { name: /urlop|zasiłek/i })
    expect(within(cards[0]).getByText('Anna')).toBeInTheDocument()
    expect(within(cards[1]).getByText('Ty')).toBeInTheDocument()
    expect(ANNA_ID).toBe('user-nowak-anna')
  })

  it('bez wniosków: pusty stan i polecane wnioski z linkami do kreatora', async () => {
    routes({ 'GET /api/applications': [], 'GET /api/mail/threads': [] })
    renderList()
    expect(await screen.findByText(/nie macie wniosków w toku/i)).toBeInTheDocument()
    const next = screen.getByRole('region', { name: /polecane następne/i })
    expect(within(next).getAllByRole('link').map((l) => l.getAttribute('href'))).toEqual([
      '/wnioski/nowy?form=URLOP-MAC-ROD',
      '/wnioski/nowy?form=ZAM',
    ])
    expect(screen.getByRole('link', { name: /nowy/i, exact: false } as never)).toHaveAttribute('href', '/wnioski/nowy')
  })

  it('błąd listy pokazuje komunikat', async () => {
    routes({ 'GET /api/applications': new ApiError(500, 'Coś poszło nie tak po naszej stronie.') })
    renderList()
    expect(await screen.findByRole('alert')).toHaveTextContent('Coś poszło nie tak po naszej stronie.')
  })
})
