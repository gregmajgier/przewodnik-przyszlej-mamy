import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { render } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../lib/api'
import { routeApi } from '../../test/routeApi'
import BenefitsPage from './BenefitsPage'
import type { BenefitMatch, MatchStatus } from './types'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

function row(id: string, name: string, status: MatchStatus, extra: Partial<BenefitMatch['match']> = {}): BenefitMatch {
  return {
    benefit: {
      id, name, scope: 'national', unit_id: null, category: 'benefit', description: `Opis ${name}`,
      amount_text: null, annual_value_estimate: null, how_to_apply: 'x', form_codes: [],
      source_url: 'https://example.gov.pl', extra_text: null, verify: false, tags: [],
    },
    match: { status, reasons: status === 'no' ? [] : ['mieszkasz w Krakowie'], unmet: status === 'no' ? ['Powód odrzucenia'] : [], questions: [], eligible_children: 1, ...extra },
    deadline_date: null,
  }
}

const ROWS: BenefitMatch[] = [
  row('a', 'Świadczenie A', 'fits'),
  row('b', 'Świadczenie B', 'maybe', { questions: [{ condition_id: 'q1', text: 'Czy tak?' }] }),
  row('c', 'Świadczenie C', 'no'),
]

function renderPage() {
  return render(
    <MemoryRouter>
      <BenefitsPage />
    </MemoryRouter>,
  )
}

describe('BenefitsPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('grupuje: pasuje, może przysługiwać; niepasujące są schowane', async () => {
    routeApi({ 'GET /api/benefits': ROWS })
    renderPage()
    expect(await screen.findByRole('heading', { name: 'Świadczenie A' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /pasuje do was/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /może ci przysługiwać/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Świadczenie B' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Świadczenie C' })).not.toBeInTheDocument()
  })

  it('„Pokaż pozostałe” rozwija niepasujące z powodem', async () => {
    routeApi({ 'GET /api/benefits': ROWS })
    renderPage()
    const toggle = await screen.findByRole('button', { name: /pokaż pozostałe \(1\)/i })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(toggle)
    expect(screen.getByRole('heading', { name: 'Świadczenie C' })).toBeInTheDocument()
    expect(screen.getByText(/Powód odrzucenia/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /ukryj pozostałe/i })).toHaveAttribute('aria-expanded', 'true')
  })

  it('odpowiedź tak/nie wysyła POST i aktualizuje kartę', async () => {
    const mocked = routeApi({
      'GET /api/benefits': ROWS,
      'POST /api/benefits/b/answers': row('b', 'Świadczenie B', 'fits'),
    })
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Tak' }))
    await waitFor(() =>
      expect(mocked).toHaveBeenCalledWith('/api/benefits/b/answers', {
        method: 'POST',
        body: { condition_id: 'q1', answer: true },
      }),
    )
    // B przeszło do grupy „pasuje” (dwa nagłówki świadczeń w jednej grupie, brak grupy „może”)
    await waitFor(() => expect(screen.queryByRole('heading', { name: /może ci przysługiwać/i })).not.toBeInTheDocument())
    const fitsGroup = screen.getByRole('region', { name: /pasuje do was/i })
    expect(within(fitsGroup).getByRole('heading', { name: 'Świadczenie B' })).toBeInTheDocument()
  })

  it('pokazuje błąd API po polsku', async () => {
    routeApi({ 'GET /api/benefits': new ApiError(404, 'Nie należysz jeszcze do żadnej rodziny.') })
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent('Nie należysz jeszcze do żadnej rodziny.')
  })

  it('pusty stan, gdy nic nie pasuje', async () => {
    routeApi({ 'GET /api/benefits': [row('c', 'Świadczenie C', 'no')] })
    renderPage()
    expect(await screen.findByText(/na razie nic nie pasuje/i)).toBeInTheDocument()
  })
})
