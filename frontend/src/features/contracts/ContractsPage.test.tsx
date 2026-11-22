import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../lib/api'
import { renderWithSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import ContractsPage from './ContractsPage'
import RisksPanel from './RisksPanel'
import type { Contract, ScanResult } from './types'
import { RisksWidget } from './RisksPanel'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

const SCAN: ScanResult = {
  draft_id: 'contract-1',
  filename: 'umowa.pdf',
  draft: {
    kind: 'employment',
    employer_name: 'Krakowskie Centrum Usług Wspólnych Sp. z o.o.',
    employer_address: null,
    employer_email: 'kadry@kcuw.example.pl',
    position: 'Specjalista',
    fte: 1,
    gross_monthly: 7850,
    start_date: '2021-11-21',
    end_date: null,
    indefinite: true,
    voluntary_sickness: null,
    missing: ['employer_address'],
  },
}

const CONFIRMED: Contract = {
  ...SCAN.draft,
  employer_address: 'ul. Przykładowa 12, Kraków',
  missing: [],
  id: 'contract-1',
  user_id: 'user-nowak-anna',
  family_id: 'family-1',
  filename: 'umowa.pdf',
  confirmed: true,
  created_at: '2026-11-21T10:00:00Z',
}

async function uploadFile() {
  const input = screen.getByLabelText('Plik z umową')
  await userEvent.upload(input, new File(['%PDF-1.4'], 'umowa.pdf', { type: 'application/pdf' }))
  await userEvent.click(screen.getByRole('button', { name: 'Odczytaj umowę' }))
}

describe('ContractsPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('po wgraniu pokazuje wyciągnięte dane do sprawdzenia', async () => {
    const api = routeApi({ 'GET /api/contracts': [], 'GET /api/risks': [], 'POST /api/contracts/scan': SCAN })
    renderWithSession(<ContractsPage />)
    await screen.findByText(/Nie dodaliście jeszcze/)
    await uploadFile()
    expect(await screen.findByRole('heading', { name: 'Sprawdź dane umowy' })).toBeInTheDocument()
    expect(screen.getByLabelText('Pracodawca / zleceniodawca')).toHaveValue(SCAN.draft.employer_name)
    expect(screen.getByLabelText('Wynagrodzenie brutto miesięcznie (zł)')).toHaveValue(7850)
    const scanCall = api.mock.calls.find(([p]) => p === '/api/contracts/scan')
    expect(scanCall?.[1]?.body).toBeInstanceOf(FormData)
  })

  it('podświetla brakujące pola', async () => {
    routeApi({ 'GET /api/contracts': [], 'GET /api/risks': [], 'POST /api/contracts/scan': SCAN })
    renderWithSession(<ContractsPage />)
    await screen.findByText(/Nie dodaliście jeszcze/)
    await uploadFile()
    const address = await screen.findByLabelText('Adres pracodawcy')
    expect(address).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByTestId('field-employer_address')).toHaveClass('field-missing')
    expect(screen.getByLabelText('Pracodawca / zleceniodawca')).not.toHaveAttribute('aria-invalid')
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
    await screen.findByText(/Nie dodaliście jeszcze/)
    await uploadFile()
    const address = await screen.findByLabelText('Adres pracodawcy')
    fireEvent.change(address, { target: { value: 'ul. Przykładowa 12, Kraków' } })
    await userEvent.click(screen.getByRole('button', { name: 'Zatwierdź' }))
    await waitFor(() => expect(screen.getByText(/Plik: umowa.pdf/)).toBeInTheDocument())
    const call = api.mock.calls.find(([p]) => p === '/api/contracts/contract-1/confirm')
    expect(call?.[1]?.body).toMatchObject({ employer_address: 'ul. Przykładowa 12, Kraków' })
  })

  it('pokazuje komunikat limitu 429 z API', async () => {
    routeApi({
      'GET /api/contracts': [],
      'GET /api/risks': [],
      'POST /api/contracts/scan': new ApiError(429, 'Zbyt wiele zapytań do asystenta. Spróbuj za chwilę.'),
    })
    renderWithSession(<ContractsPage />)
    await screen.findByText(/Nie dodaliście jeszcze/)
    await uploadFile()
    expect(await screen.findByRole('alert')).toHaveTextContent('Zbyt wiele zapytań do asystenta')
  })

  it('usuwa tylko własne umowy (przycisk tylko u właściciela)', async () => {
    routeApi({
      'GET /api/contracts': [CONFIRMED, { ...CONFIRMED, id: 'c-2', user_id: 'user-nowak-piotr', filename: null }],
      'GET /api/risks': [],
    })
    renderWithSession(<ContractsPage />)
    await screen.findByText(/Plik: umowa.pdf/)
    expect(screen.getAllByRole('button', { name: 'Usuń' })).toHaveLength(1)
  })
})

describe('ContractsPage — umowy z e-teczki pracodawcy', () => {
  beforeEach(() => vi.clearAllMocks())

  it('niedodaną umowę można dodać jednym kliknięciem', async () => {
    const doc = {
      id: 'umowa-o-prace-kcuw',
      title: 'Umowa o pracę na czas nieokreślony',
      filename: 'umowa.pdf',
      kind: 'employment',
      employer_name: CONFIRMED.employer_name,
      position: 'Specjalistka ds. kadr i płac',
      start_date: '2021-11-22',
      end_date: null,
      indefinite: true,
      contract_id: null,
    }
    let added = false
    const api = routeApi({
      'GET /api/contracts': () => (added ? [{ ...CONFIRMED, source_doc_id: doc.id }] : []),
      'GET /api/risks': [],
      'GET /api/contracts/documents': () => [{ ...doc, contract_id: added ? 'contract-1' : null }],
      [`POST /api/contracts/documents/${doc.id}/import`]: () => {
        added = true
        return { ...CONFIRMED, source_doc_id: doc.id }
      },
    })
    renderWithSession(<ContractsPage />)
    const section = await screen.findByRole('region', { name: /umowy z e-teczki pracodawcy/i })
    expect(section).toHaveTextContent('Specjalistka ds. kadr i płac')
    await userEvent.click(screen.getByRole('button', { name: /^dodaj$/i }))
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith(`/api/contracts/documents/${doc.id}/import`, { method: 'POST' }),
    )
    await waitFor(() =>
      expect(screen.queryByRole('region', { name: /umowy z e-teczki pracodawcy/i })).not.toBeInTheDocument(),
    )
    expect(await screen.findByRole('button', { name: /podgląd pdf/i })).toBeInTheDocument()
  })
})

describe('RisksPanel', () => {
  beforeEach(() => vi.clearAllMocks())

  it('bez ryzyk pokazuje „Brak ostrzeżeń”', async () => {
    routeApi({ 'GET /api/risks': [] })
    renderWithSession(<RisksWidget />)
    expect(await screen.findByText(/Brak ostrzeżeń/)).toBeInTheDocument()
  })

  it('pokazuje ryzyko z akcją i terminem', async () => {
    routeApi({
      'GET /api/risks': [
        {
          id: 'r1',
          severity: 'high',
          title: 'Brak zasiłku macierzyńskiego przy umowie zlecenia',
          explanation: 'Bez ubezpieczenia chorobowego nie dostaniesz zasiłku.',
          action: 'Zgłoś się do dobrowolnego ubezpieczenia.',
          deadline: '2026-12-01',
          user_id: 'user-nowak-anna',
          source_ref: 'c1',
        },
      ],
    })
    renderWithSession(<RisksPanel />)
    expect(await screen.findByText('Pilne')).toBeInTheDocument()
    expect(screen.getByText(/Zgłoś się do dobrowolnego/)).toBeInTheDocument()
    expect(screen.getByText(/01\.12\.2026/)).toBeInTheDocument()
    expect(screen.getByRole('listitem')).toHaveClass('risk-high')
  })
})
