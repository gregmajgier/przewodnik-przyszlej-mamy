import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { routeApi } from '../../test/routeApi'
import widget from './widget'
import type { BenefitMatch } from './types'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

function row(id: string, name: string, status: 'fits' | 'maybe' | 'no'): BenefitMatch {
  return {
    benefit: { id, name, scope: 'national', unit_id: null, category: 'benefit', description: '', amount_text: null, annual_value_estimate: null, how_to_apply: '', form_codes: [], source_url: 'https://x.pl', extra_text: null, verify: false, tags: [] },
    match: { status, reasons: [], unmet: [], questions: [], eligible_children: 0 },
    deadline_date: null,
  }
}

describe('widget świadczeń', () => {
  beforeEach(() => vi.clearAllMocks())

  it('ma kolejność i komponent', () => {
    expect(widget.order).toBeTypeOf('number')
    expect(widget.Component).toBeTypeOf('function')
  })

  it('pokazuje liczby i pierwsze pasujące świadczenia oraz link do pełnej listy', async () => {
    routeApi({
      'GET /api/benefits': [
        row('a', 'Rodzina 800+', 'fits'),
        row('b', 'Ulga prorodzinna', 'fits'),
        row('c', 'Dobry Start', 'maybe'),
        row('d', 'Inne', 'no'),
      ],
    })
    const W = widget.Component
    render(
      <MemoryRouter>
        <W />
      </MemoryRouter>,
    )
    expect(await screen.findByText('Rodzina 800+')).toBeInTheDocument()
    expect(screen.getByText(/2 pasuje/)).toBeInTheDocument()
    expect(screen.getByText(/1 może przysługiwać/)).toBeInTheDocument()
    expect(screen.queryByText('Inne')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /wszystkie świadczenia/i })).toHaveAttribute('href', '/swiadczenia')
  })
})
