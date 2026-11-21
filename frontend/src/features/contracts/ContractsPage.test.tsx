import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../lib/api'
import { ANNA, renderWithSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import ContractsPage from './ContractsPage'
import RisksPanel from './RisksPanel'
import widget from './widget'
import type { Contract, ContractDraft, Risk, ScanResult } from './types'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

const DRAFT: ContractDraft = {
  kind: 'mandate',
  employer_name: 'Studio Foto s.c.',
  employer_address: null,
  employer_email: null,
  position: 'Fotograf',
  fte: null,
  gross_monthly: 4000,
  start_date: '2026-01-01',
  end_date: null,
  indefinite: true,
  voluntary_sickness: null,
  missing: ['employer_address', 'fte', 'voluntary_sickness'],
}
const SCAN: ScanResult = { draft_id: 'contract-1', draft: DRAFT, filename: 'umowa.pdf' }
const CONFIRMED: Contract = {
  ...DRAFT,
  id: 'contract-1',
  user_id: ANNA.id,
  family_id: 'f1',
  filename: 'umowa.pdf',
  confirmed: true,
  created_at: '2026-11-21T10:00:00Z',
  missing: [],
}
const RISK: Risk = {
  id: 'r1',
  severity: 'high',
  title: 'Brak zasiłku macierzyńskiego przy umowie zlecenia',
  explanation: 'Bez chorobowego nie dostaniesz zasiłku.',
  action: 'Zgłoś się do dobrowolnego ubezpieczenia chorobowego.',
  deadline: '2026-11-20',
  user_id: ANNA.id,
  source_ref: 'contract-1',
}

const pdf = () => new File(['%PDF-1.4'], 'umowa.pdf', { type: 'application/pdf' })

describe('ContractsPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('po wgraniu pliku pokazuje wyciągnięte dane do sprawdzenia', async () => {
    routeApi({
      'GET /api/contracts': [],
      'GET /api/risks': [],
      'POST /api/contracts/scan': SCAN,
    })
    renderWithSession(<ContractsPage />)
    await userEvent.upload(await screen.findByLabelText(/wybierz umowy/i), pdf())
    expect(await screen.findByRole('heading', { name: /sprawdź, co znaleźliśmy/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/pracodawca \(zleceniodawca\)/i)).toHaveValue('Studio Foto s.c.')
    expect(screen.getByLabelText('Stanowisko')).toHaveValue('Fotograf')
    expect(screen.getByLabelText(/wynagrodzenie brutto/i)).toHaveValue('4000')
  })

  it('podświetla brakujące pola', async () => {
    routeApi({ 'GET /api/contracts': [], 'GET /api/risks': [], 'POST /api/contracts/scan': SCAN })
    renderWithSession(<ContractsPage />)
    await userEvent.upload(await screen.findByLabelText(/wybierz umowy/i), pdf())
    const address = await screen.findByLabelText('Adres pracodawcy')
    expect(address).toHaveAttribute('data-missing', 'true')
    expect(address).toHaveAccessibleDescription(/uzupełnij/i)
    expect(screen.getByLabelText(/wymiar etatu/i)).toHaveAttribute('data-missing', 'true')
    expect(screen.getByLabelText('Stanowisko')).toHaveAttribute('data-missing', 'false')
    // uzupełnienie pola zdejmuje podświetlenie
    await userEvent.type(address, 'ul. Długa 1')
    expect(address).toHaveAttribute('data-missing', 'false')
  })

  it('zatwierdzenie wywołuje confirm z poprawionymi danymi i odświeża listę', async () => {
    let confirmed = false
    const api = routeApi({
      'GET /api/contracts': () => (confirmed ? [CONFIRMED] : []),
      'GET /api/risks': [],
      'POST /api/contracts/scan': SCAN,
      'POST /api/contracts/contract-1/confirm': () => {
        confirmed = true
        return CONFIRMED
      },
    })
    renderWithSession(<ContractsPage />)
    await userEvent.upload(await screen.findByLabelText(/wybierz umowy/i), pdf())
    await userEvent.selectOptions(await screen.findByLabelText(/dobrowolne ubezpieczenie chorobowe/i), 'no')
    await userEvent.type(screen.getByLabelText(/wymiar etatu/i), '1')
    await userEvent.click(screen.getByRole('button', { name: 'Zatwierdź' }))

    await waitFor(() => expect(screen.queryByRole('heading', { name: /sprawdź/i })).not.toBeInTheDocument())
    const call = api.mock.calls.find(([path]) => path === '/api/contracts/contract-1/confirm')!
    const body = (call[1] as { body: ContractDraft }).body
    expect(body).toMatchObject({ kind: 'mandate', employer_name: 'Studio Foto s.c.', fte: 1, voluntary_sickness: false })
    const list = await screen.findByRole('heading', { name: 'Studio Foto s.c.' })
    expect(list).toBeInTheDocument()
  })

  it('pokazuje komunikat błędu z API przy limicie 429', async () => {
    routeApi({
      'GET /api/contracts': [],
      'GET /api/risks': [],
      'POST /api/contracts/scan': new ApiError(429, 'Zbyt wiele zapytań do asystenta. Spróbuj za chwilę.'),
    })
    renderWithSession(<ContractsPage />)
    await userEvent.upload(await screen.findByLabelText(/wybierz umowy/i), pdf())
    expect(await screen.findByRole('alert')).toHaveTextContent(/Zbyt wiele zapytań do asystenta/)
  })

  it('pokazuje błąd walidacji przy zatwierdzaniu (422) i nie zamyka formularza', async () => {
    routeApi({
      'GET /api/contracts': [],
      'GET /api/risks': [],
      'POST /api/contracts/scan': SCAN,
      'POST /api/contracts/contract-1/confirm': new ApiError(422, 'Uzupełnij brakujące dane umowy: wymiar etatu lub wynagrodzenie.'),
    })
    renderWithSession(<ContractsPage />)
    await userEvent.upload(await screen.findByLabelText(/wybierz umowy/i), pdf())
    await userEvent.click(await screen.findByRole('button', { name: 'Zatwierdź' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/Uzupełnij brakujące dane umowy/)
    expect(screen.getByRole('heading', { name: /sprawdź/i })).toBeInTheDocument()
  })

  it('odrzuca zbyt duży plik bez wysyłania', async () => {
    const api = routeApi({ 'GET /api/contracts': [], 'GET /api/risks': [] })
    renderWithSession(<ContractsPage />)
    const big = new File([new Uint8Array(5 * 1024 * 1024 + 1)], 'duza.pdf', { type: 'application/pdf' })
    await userEvent.upload(await screen.findByLabelText(/wybierz umowy/i), big)
    expect(await screen.findByRole('alert')).toHaveTextContent(/za duży/)
    expect(api.mock.calls.some(([p]) => p === '/api/contracts/scan')).toBe(false)
  })

  it('lista umów: partner nie ma przycisku usuwania', async () => {
    routeApi({
      'GET /api/contracts': [{ ...CONFIRMED, user_id: 'user-nowak-piotr', filename: null }],
      'GET /api/risks': [],
    })
    renderWithSession(<ContractsPage />)
    expect(await screen.findByText(/dodana przez drugiego rodzica/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /usuń umowę/i })).not.toBeInTheDocument()
  })
})

describe('RisksPanel i widżet', () => {
  beforeEach(() => vi.clearAllMocks())

  it('widżet bez ryzyk pokazuje „Brak ostrzeżeń”', async () => {
    routeApi({ 'GET /api/risks': [] })
    renderWithSession(<widget.Component />)
    expect(await screen.findByText(/Brak ostrzeżeń/)).toBeInTheDocument()
    expect(widget.order).toBe(20)
  })

  it('pokazuje ryzyka z akcją, terminem i wagą', async () => {
    routeApi({ 'GET /api/risks': [RISK, { ...RISK, id: 'r2', severity: 'info', title: 'Umowa się kończy', action: null, deadline: null }] })
    renderWithSession(<RisksPanel />)
    const items = await screen.findAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(items[0]).toHaveAttribute('data-severity', 'high')
    expect(within(items[0]).getByText('Ważne')).toBeInTheDocument()
    expect(within(items[0]).getByText(/Zgłoś się do dobrowolnego/)).toBeInTheDocument()
    expect(within(items[0]).getByText(/20\.11\.2026/)).toBeInTheDocument()
    expect(within(items[1]).getByText('Informacja')).toBeInTheDocument()
    expect(within(items[1]).queryByText(/Co zrobić/)).not.toBeInTheDocument()
  })
})
