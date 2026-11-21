import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import MailPage from './MailPage'
import MailSettings from './MailSettings'
import type { MailThread } from './types'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

const THREAD: MailThread = {
  application: {
    id: 'a1', form_code: 'URLOP-MAC-ROD', status: 'accepted', applicant_id: 'user-nowak-anna',
    applicant_name: 'Anna Nowak', recipient_email: 'kadry@kcuw.example.pl', sent_at: '2026-11-20T10:00:00Z',
  },
  needs_review: false,
  messages: [
    {
      id: 'm1', folder: 'inbox', from_addr: 'kadry@kcuw.example.pl', to_addr: '', subject: 'Re: Wniosek — zatwierdzony',
      body: 'Wniosek zatwierdzony.', received_at: '2026-11-20T11:00:00Z', classification_status: 'accepted',
      classification_confidence: 0.92, classification_summary: 'Wniosek został rozpatrzony pozytywnie.', needs_review: false,
    },
  ],
}

describe('Poczta', () => {
  beforeEach(() => vi.clearAllMocks())

  it('wątki pokazują status wniosku i kto go złożył', async () => {
    routeApi({ 'GET /api/mail/threads': [THREAD] })
    renderWithSession(<MailPage />)
    expect(await screen.findByRole('heading', { name: 'Wniosek URLOP-MAC-ROD' })).toBeInTheDocument()
    expect(screen.getByText('Zaakceptowany')).toBeInTheDocument()
    expect(screen.getByText(/Złożył\(a\): Anna Nowak/)).toBeInTheDocument()
  })

  it('„Symuluj odpowiedzi” wywołuje API i odświeża wątki', async () => {
    let calls = 0
    const api = routeApi({
      'GET /api/mail/threads': () => (calls++ ? [THREAD] : [{ ...THREAD, application: { ...THREAD.application, status: 'sent' } }]),
      'POST /api/mail/simulate-replies': { delivered: 2, new_messages: 2, status_changes: 2, to_review: 0 },
    })
    renderWithSession(<MailPage />)
    await screen.findByText('Wysłany')
    await userEvent.click(screen.getByRole('button', { name: 'Symuluj odpowiedzi' }))
    expect(await screen.findByText('Zaakceptowany')).toBeInTheDocument()
    expect(screen.getByText('Dostarczono odpowiedzi: 2.')).toBeInTheDocument()
    expect(api.mock.calls.some(([p]) => p === '/api/mail/simulate-replies')).toBe(true)
  })

  it('wiadomość do sprawdzenia jest oznaczona', async () => {
    routeApi({ 'GET /api/mail/threads': [{ ...THREAD, needs_review: true }] })
    renderWithSession(<MailPage />)
    expect(await screen.findByText(/sprawdź, nie zmieniliśmy statusu/)).toBeInTheDocument()
  })

  it('ustawienia pokazują zakres czytania i „Gmail podłączony”', async () => {
    routeApi({
      'GET /api/mail/status': {
        connected: true, provider: 'gmail-sim', simulated: true, address: 'anna.nowak@gmail.com',
        scope_note: 'Czytamy tylko wiadomości w sprawie wysłanych przez Was wniosków.',
      },
    })
    renderWithSession(<MailSettings />)
    expect(await screen.findByRole('heading', { name: /Gmail podłączony/ })).toBeInTheDocument()
    expect(screen.getByText(/Czytamy tylko wiadomości w sprawie/)).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('anna.nowak@gmail.com')).toBeInTheDocument())
    expect(screen.getByText(/Wkrótce: przypomnienia mailem i SMS-em/)).toBeInTheDocument()
  })
})
