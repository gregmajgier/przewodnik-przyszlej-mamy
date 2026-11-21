import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../lib/api'
import { makeSession, renderWithSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import type { Benefit, BenefitMatch } from './types'
import widget from './widget'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

const b = (id: string, name: string, amount: string | null = null): Benefit => ({
  id, name, scope: 'national', unit_id: null, category: 'benefit', description: '', amount_text: amount,
  annual_value_estimate: null, how_to_apply: '', form_codes: [], source_url: 'https://www.gov.pl', extra_text: null, verify: false,
})
const match = (benefit: Benefit, status: 'fits' | 'maybe' | 'no'): BenefitMatch => ({ benefit, match: { status, reasons: [], unmet: [], questions: [] } })

const Widget = widget.Component

beforeEach(() => vi.clearAllMocks())

describe('kafelek „Świadczenia” na dashboardzie', () => {
  it('liczy dopasowania i pokazuje najważniejsze (tylko pasujące) z kwotą', async () => {
    routeApi({
      'GET /api/benefits': [
        match(b('a', '800 plus', '800 zł miesięcznie'), 'fits'),
        match(b('b', 'Karta Dużej Rodziny'), 'maybe'),
        match(b('c', 'Za życiem'), 'no'),
      ],
    })
    renderWithSession(<Widget />, { session: makeSession() })
    expect(await screen.findByText(/pasuje 1 · może ci przysługiwać 1/i)).toBeInTheDocument()
    expect(screen.getByText('800 plus')).toBeInTheDocument()
    expect(screen.getByText(/800 zł miesięcznie/)).toBeInTheDocument()
    expect(screen.queryByText('Karta Dużej Rodziny')).not.toBeInTheDocument()
    expect(screen.queryByText('Za życiem')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /zobacz wszystkie świadczenia/i })).toHaveAttribute('href', '/swiadczenia')
  })

  it('pokazuje najwyżej cztery pozycje', async () => {
    routeApi({ 'GET /api/benefits': Array.from({ length: 6 }, (_, i) => match(b(`n${i}`, `Świadczenie ${i}`), 'fits')) })
    renderWithSession(<Widget />, { session: makeSession() })
    await screen.findByText(/pasuje 6/i)
    expect(screen.getAllByRole('listitem')).toHaveLength(4)
  })

  it('błąd ładowania nie psuje panelu', async () => {
    routeApi({ 'GET /api/benefits': new ApiError(500, 'błąd') })
    renderWithSession(<Widget />, { session: makeSession() })
    expect(await screen.findByText(/nie udało się wczytać świadczeń/i)).toBeInTheDocument()
  })
})
