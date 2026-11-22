import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, apiBlob, ApiError } from '../../lib/api'
import { ANNA, makeSession, renderWithSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import type { Application } from './types'
import ApplicationWizard from './ApplicationWizard'
import { FORMS, makeApp, makeFamily, PIOTR } from './testData'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
  apiBlob: vi.fn(),
}))

// Agent ma własne testy (AgentFrame.test) — tu sprawdzamy tylko, że kreator go osadza i przyjmuje jego wynik.
vi.mock('../portal-sim/AgentFrame', () => ({
  default: ({ applicationId, onSubmitted }: { applicationId: string; onSubmitted: (a: Application) => void }) => (
    <button type="button" onClick={() => onSubmitted({ ...makeApp({ channel: 'portal_agent' }), id: applicationId, status: 'sent', sent_at: '2026-11-21T10:30:00Z' })}>
      Agent: złóż w makiecie
    </button>
  ),
}))

const FAMILY = makeFamily(ANNA)
const BASE = '/api/applications/app-1'
const session = (over = {}) => makeSession({ family: FAMILY, ...over })

function renderWizard(initial: Application, extra: Record<string, unknown> = {}, sess = session()) {
  const mocked = routeApi({
    [`GET ${BASE}`]: initial,
    'GET /api/applications/forms': FORMS,
    ...extra,
  })
  vi.mocked(apiBlob).mockResolvedValue(new Blob(['%PDF-1.4'], { type: 'application/pdf' }))
  renderWithSession(
    <Routes>
      <Route path="/wnioski/:id" element={<ApplicationWizard applicationId="app-1" />} />
      <Route path="/wnioski" element={<p>Lista wniosków</p>} />
    </Routes>,
    { route: '/wnioski/app-1', session: sess },
  )
  return mocked
}

const currentStep = () => screen.getByRole('list', { name: /postęp składania wniosku/i }).querySelector('[aria-current="step"]')?.textContent ?? ''

beforeEach(() => {
  vi.clearAllMocks()
  URL.createObjectURL = vi.fn(() => 'blob:pdf-preview')
  URL.revokeObjectURL = vi.fn()
})

describe('ApplicationWizard — krok 1: brakujące dane', () => {
  const needsInput = makeApp({
    status: 'needs_input',
    values: { first_name: 'Anna' },
    missing: [
      { field_id: 'employer_email', label: 'Adres e-mail pracodawcy (dział kadr)', type: 'text', choices: null },
      { field_id: 'leave_start', label: 'Początek urlopu macierzyńskiego', type: 'date', choices: null },
    ],
  })

  it('zadaje pytania po jednym, a puste pole blokuje przejście dalej', async () => {
    renderWizard(needsInput)
    expect(await screen.findByRole('heading', { name: /brakuje jeszcze 2 informacji/i })).toBeInTheDocument()
    expect(currentStep()).toContain('Dane')
    expect(screen.getByText(/pytanie 1 z 2/i)).toBeInTheDocument()
    expect(screen.getByLabelText('Adres e-mail pracodawcy (dział kadr)')).toBeInTheDocument()
    expect(screen.queryByLabelText('Początek urlopu macierzyńskiego')).not.toBeInTheDocument() // kolejne pytanie dopiero po odpowiedzi
    const next = screen.getByRole('button', { name: /dalej/i })
    expect(next).toBeDisabled()
    await userEvent.type(screen.getByLabelText(/adres e-mail pracodawcy/i), '   ')
    expect(next).toBeDisabled() // same spacje to nadal brak danych
  })

  it('zapisuje odpowiedź w API i przechodzi do kolejnego pytania, a po ostatnim — do podglądu', async () => {
    const afterFirst = { ...needsInput, missing: [needsInput.missing[1]], recipient_email: 'kadry@kcuw.example.pl' }
    const complete = makeApp({ status: 'draft' })
    const answers: Application[] = [afterFirst, complete]
    const mocked = renderWizard(needsInput, { [`POST ${BASE}/answers`]: () => answers.shift() })

    await userEvent.type(await screen.findByLabelText(/adres e-mail pracodawcy/i), 'kadry@kcuw.example.pl')
    await userEvent.click(screen.getByRole('button', { name: /dalej/i }))
    await waitFor(() =>
      expect(mocked).toHaveBeenCalledWith(`${BASE}/answers`, { method: 'POST', body: { answers: { employer_email: 'kadry@kcuw.example.pl' } } }),
    )
    expect(await screen.findByLabelText('Początek urlopu macierzyńskiego')).toHaveValue('') // czyste pole na nowe pytanie

    await userEvent.type(screen.getByLabelText('Początek urlopu macierzyńskiego'), '20012027') // DD.MM.RRRR
    await userEvent.click(screen.getByRole('button', { name: /dalej/i }))
    expect(await screen.findByRole('heading', { name: /sprawdź wniosek/i })).toBeInTheDocument()
    expect(currentStep()).toContain('Podgląd')
  })

  it('błąd walidacji z API pokazuje komunikat i zostawia pytanie', async () => {
    renderWizard(needsInput, { [`POST ${BASE}/answers`]: new ApiError(422, 'Pole „Adres e-mail pracodawcy”: podaj poprawny adres e-mail.') })
    await userEvent.type(await screen.findByLabelText(/adres e-mail pracodawcy/i), 'zly')
    await userEvent.click(screen.getByRole('button', { name: /dalej/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/podaj poprawny adres e-mail/i)
    expect(screen.getByLabelText(/adres e-mail pracodawcy/i)).toHaveValue('zly')
  })

  it('pytanie tak/nie ma dwa przyciski', async () => {
    renderWizard(makeApp({ status: 'needs_input', missing: [{ field_id: 'certificate_confirmed', label: 'Czy masz zaświadczenie lekarskie?', type: 'bool', choices: null }] }), {
      [`POST ${BASE}/answers`]: makeApp(),
    })
    await userEvent.click(await screen.findByRole('button', { name: 'Tak' }))
    expect(vi.mocked(api)).toHaveBeenCalledWith(`${BASE}/answers`, { method: 'POST', body: { answers: { certificate_confirmed: true } } })
  })
})

describe('ApplicationWizard — krok 2: podgląd', () => {
  it('pokazuje etykiety i wartości (daty po polsku) oraz podgląd PDF', async () => {
    renderWizard(makeApp())
    expect(await screen.findByRole('heading', { name: /sprawdź wniosek/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: /urlop macierzyński i rodzicielski/i })).toBeInTheDocument()
    expect(screen.getByText('Nazwa pracodawcy')).toBeInTheDocument()
    expect(screen.getByText('Krakowskie Centrum Usług Wspólnych')).toBeInTheDocument()
    expect(screen.getByText('20.01.2027')).toBeInTheDocument()
    const pdf = await screen.findByTitle('Podgląd wniosku (PDF)')
    expect(pdf).toHaveAttribute('src', 'blob:pdf-preview')
    expect(apiBlob).toHaveBeenCalledWith(`${BASE}/pdf`)
  })

  it('pozwala poprawić pole i zapisuje zmianę przez PATCH', async () => {
    const edited = makeApp({ values: { ...makeApp().values, employer_name: 'Nowa Firma sp. z o.o.' } })
    const mocked = renderWizard(makeApp(), { [`PATCH ${BASE}`]: edited })
    await userEvent.click(await screen.findByRole('button', { name: 'Zmień: Nazwa pracodawcy' }))
    const input = screen.getByLabelText('Nazwa pracodawcy')
    await userEvent.clear(input)
    await userEvent.type(input, 'Nowa Firma sp. z o.o.')
    await userEvent.click(screen.getByRole('button', { name: 'Zapisz' }))
    await waitFor(() =>
      expect(mocked).toHaveBeenCalledWith(BASE, { method: 'PATCH', body: { values: { employer_name: 'Nowa Firma sp. z o.o.' } } }),
    )
    expect(await screen.findByText('Nowa Firma sp. z o.o.')).toBeInTheDocument()
  })

  it('zmiana kanału (e-mail → PDF) idzie przez PATCH i odświeża podgląd', async () => {
    const mocked = renderWizard(makeApp(), { [`PATCH ${BASE}`]: makeApp({ channel: 'pdf_download', recipient_email: null, recipient_domain: null }) })
    const pdf = await screen.findByRole('radio', { name: /pdf do pobrania/i })
    expect(screen.getByRole('radio', { name: /e-mail do pracodawcy/i })).toHaveAttribute('aria-checked', 'true')
    await userEvent.click(pdf)
    await waitFor(() => expect(mocked).toHaveBeenCalledWith(BASE, { method: 'PATCH', body: { channel: 'pdf_download' } }))
    await waitFor(() => expect(screen.getByRole('radio', { name: /pdf do pobrania/i })).toHaveAttribute('aria-checked', 'true'))
  })

  it('wniosek przez portal nie pobiera PDF (nie ma wersji PDF)', async () => {
    renderWizard(makeApp({ form_code: 'ZAM', channel: 'portal_agent' }))
    await screen.findByRole('heading', { name: /sprawdź wniosek/i })
    expect(apiBlob).not.toHaveBeenCalled()
    expect(screen.queryByTitle('Podgląd wniosku (PDF)')).not.toBeInTheDocument()
  })
})

describe('ApplicationWizard — krok 3: podpis i wysyłka', () => {
  async function toSendStep() {
    await userEvent.click(await screen.findByRole('button', { name: /wszystko się zgadza/i }))
  }

  it('podpis w modalu Profilu Zaufanego, a potem „Wyślij” wyłącza się po kliknięciu i wysyła tylko raz', async () => {
    const signed = makeApp({ status: 'ready', signed_at: '2026-11-21T10:05:00Z' })
    let release: (a: Application) => void = () => {}
    const submit = vi.fn(() => new Promise<Application>((resolve) => (release = resolve)))
    const mocked = renderWizard(makeApp(), { [`POST ${BASE}/sign`]: signed, [`POST ${BASE}/submit`]: submit })
    await toSendStep()

    expect(currentStep()).toContain('Złożenie')
    expect(screen.getByText('kadry@kcuw.example.pl')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Wyślij' })).not.toBeInTheDocument() // najpierw podpis

    await userEvent.click(screen.getByRole('button', { name: /podpisz profilem zaufanym/i }))
    const dialog = screen.getByRole('dialog', { name: /podpisz profilem zaufanym/i })
    expect(within(dialog).queryByText(/symulacja/i)).not.toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Podpisz' }))
    await waitFor(() => expect(mocked).toHaveBeenCalledWith(`${BASE}/sign`, { method: 'POST' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(screen.getByText(/podpisano profilem zaufanym/i)).toBeInTheDocument()

    const send = screen.getByRole('button', { name: 'Wyślij' })
    await userEvent.click(send)
    expect(send).toBeDisabled() // od razu po kliknięciu
    await userEvent.click(send)
    expect(submit).toHaveBeenCalledTimes(1)

    release(makeApp({ status: 'sent', signed_at: signed.signed_at, sent_at: '2026-11-21T10:06:00Z', thread_id: 'thread-1' }))
    expect(await screen.findByRole('heading', { name: /wniosek złożony/i })).toBeInTheDocument()
    expect(screen.getByText('kcuw.example.pl')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /kalendarz/i })).toHaveAttribute('href', '/kalendarz')
  })

  it('anulowanie modalu (przycisk i Escape) nic nie podpisuje', async () => {
    const mocked = renderWizard(makeApp())
    await toSendStep()
    await userEvent.click(screen.getByRole('button', { name: /podpisz profilem zaufanym/i }))
    await userEvent.click(screen.getByRole('button', { name: 'Anuluj' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /podpisz profilem zaufanym/i }))
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(mocked).not.toHaveBeenCalledWith(`${BASE}/sign`, expect.anything())
  })

  it('błąd wysyłki pokazuje komunikat i pozwala spróbować ponownie', async () => {
    const signed = makeApp({ status: 'ready', signed_at: '2026-11-21T10:05:00Z' })
    renderWizard(signed, { [`POST ${BASE}/submit`]: new ApiError(502, 'Nie udało się wysłać wiadomości. Spróbuj ponownie za chwilę.') })
    await toSendStep()
    await userEvent.click(await screen.findByRole('button', { name: 'Wyślij' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/nie udało się wysłać wiadomości/i)
    expect(screen.getByRole('button', { name: 'Wyślij' })).toBeEnabled()
  })

  it('kanał PDF: „Złóż wniosek” składa go w ZUS (symulacja), a PDF można też pobrać', async () => {
    const signed = makeApp({ channel: 'pdf_download', status: 'ready', signed_at: '2026-11-21T10:05:00Z', recipient_email: null })
    const sent = makeApp({
      channel: 'pdf_download',
      status: 'sent',
      sent_at: '2026-11-21T10:06:00Z',
      recipient_email: 'wnioski@zus.pl',
      recipient_domain: 'zus.pl',
    })
    const mocked = renderWizard(signed, { [`POST ${BASE}/submit`]: sent })
    await toSendStep()
    expect(screen.getByRole('button', { name: /pobierz pdf/i })).toBeInTheDocument()
    expect(screen.queryByText(/wyślemy ten wniosek/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /oznacz jako złożony/i })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /^złóż wniosek$/i }))
    expect(await screen.findByText(/złożyliśmy go w ZUS przez eZUS/i)).toBeInTheDocument()
    expect(mocked).toHaveBeenCalledWith(`${BASE}/submit`, { method: 'POST' })
  })

  it('kanał portalu: osadza agenta i przyjmuje wynik jego pracy', async () => {
    renderWizard(makeApp({ form_code: 'ZAM', channel: 'portal_agent', recipient_email: null }))
    await toSendStep()
    expect(screen.queryByRole('button', { name: /podpisz profilem zaufanym/i })).not.toBeInTheDocument() // portal podpisuje się w makiecie
    await userEvent.click(screen.getByRole('button', { name: /agent: złóż w makiecie/i }))
    expect(await screen.findByText(/złożyliśmy go przez formularz online/i)).toBeInTheDocument()
  })

  it('można wrócić z kroku wysyłki do podglądu', async () => {
    renderWizard(makeApp())
    await toSendStep()
    await userEvent.click(screen.getByRole('button', { name: /wróć do podglądu/i }))
    expect(await screen.findByRole('heading', { name: /sprawdź wniosek/i })).toBeInTheDocument()
  })
})

describe('ApplicationWizard — stany szczególne', () => {
  it('wysłany wniosek od razu pokazuje ekran „gotowe”', async () => {
    renderWizard(makeApp({ status: 'sent', sent_at: '2026-11-21T10:06:00Z' }))
    expect(await screen.findByRole('heading', { name: /wniosek złożony/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /wróć do listy wniosków/i })).toHaveAttribute('href', '/wnioski')
  })

  it('anulowany wniosek (np. tryb straty) nie pozwala niczego wysłać', async () => {
    renderWizard(makeApp({ status: 'cancelled' }))
    expect(await screen.findByRole('heading', { name: /wniosek anulowany/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /wyślij|podpisz/i })).not.toBeInTheDocument()
  })

  it('drugi rodzic widzi wniosek tylko do odczytu', async () => {
    renderWizard(makeApp(), {}, session({ user: PIOTR }))
    expect(await screen.findByRole('heading', { name: /wniosek składa anna nowak/i })).toBeInTheDocument()
    expect(screen.getByText('Krakowskie Centrum Usług Wspólnych')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /dalej|zmień|podpisz|wyślij/i })).not.toBeInTheDocument()
  })

  it('cudzy lub nieistniejący wniosek (404) pokazuje stan „Tego wniosku już nie ma” z drogą dalej', async () => {
    routeApi({ [`GET ${BASE}`]: new ApiError(404, 'Nie znaleziono takiego wniosku.'), 'GET /api/applications/forms': FORMS })
    renderWithSession(<ApplicationWizard applicationId="app-1" />, { session: session() })
    expect(await screen.findByRole('heading', { name: /tego wniosku już nie ma/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /wróć do wniosków/i })).toHaveAttribute('href', '/wnioski')
  })

  it('wniosek zniknął w trakcie podpisu (404) — zamiast błędu w oknie podpisu ten sam stan', async () => {
    renderWizard(makeApp(), { [`POST ${BASE}/sign`]: new ApiError(404, 'Nie znaleziono takiego wniosku.') })
    await userEvent.click(await screen.findByRole('button', { name: /wszystko się zgadza/i }))
    await userEvent.click(screen.getByRole('button', { name: /podpisz profilem zaufanym/i }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Podpisz' }))
    expect(await screen.findByRole('heading', { name: /tego wniosku już nie ma/i })).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /nowy wniosek/i })).toHaveAttribute('href', '/wnioski/nowy?form=URLOP-MAC-ROD')
  })
})
