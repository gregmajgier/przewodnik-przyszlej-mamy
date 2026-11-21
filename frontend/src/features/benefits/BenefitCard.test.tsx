import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import BenefitCard from './BenefitCard'
import type { BenefitMatch } from './types'

function item(over: Partial<BenefitMatch['match']> = {}, benefit: Partial<BenefitMatch['benefit']> = {}): BenefitMatch {
  return {
    benefit: {
      id: 'nat-800plus',
      name: 'Rodzina 800+',
      scope: 'national',
      unit_id: null,
      category: 'benefit',
      description: '800 zł miesięcznie na dziecko.',
      amount_text: '800 zł miesięcznie na dziecko',
      annual_value_estimate: 9600,
      how_to_apply: 'Złóż wniosek w ZUS.',
      form_codes: ['800PLUS'],
      source_url: 'https://www.zus.pl/800plus',
      extra_text: null,
      verify: false,
      tags: [],
      ...benefit,
    },
    match: { status: 'fits', reasons: ['Maja ma 7 lat', 'Antek ma 3 lata'], unmet: [], questions: [], eligible_children: 2, ...over },
    deadline_date: null,
  }
}

function setup(m: BenefitMatch, onAnswer = vi.fn()) {
  render(
    <MemoryRouter>
      <BenefitCard item={m} onAnswer={onAnswer} />
    </MemoryRouter>,
  )
  return onAnswer
}

describe('BenefitCard', () => {
  it('pasuje: nazwa, badge, „dlaczego”, kwota i link do źródła', () => {
    setup(item())
    expect(screen.getByRole('heading', { name: 'Rodzina 800+' })).toBeInTheDocument()
    expect(screen.getByText('Pasuje')).toBeInTheDocument()
    expect(screen.getByText(/Pasuje, bo Maja ma 7 lat i Antek ma 3 lata/)).toBeInTheDocument()
    expect(screen.getByText('800 zł miesięcznie na dziecko')).toBeInTheDocument()
    const src = screen.getByRole('link', { name: /źródło/i })
    expect(src).toHaveAttribute('href', 'https://www.zus.pl/800plus')
    expect(src).toHaveAttribute('rel', expect.stringContaining('noopener'))
  })

  it('„Złóż wniosek” prowadzi do kreatora wniosku z kodem formularza', () => {
    setup(item())
    expect(screen.getByRole('link', { name: /złóż wniosek/i })).toHaveAttribute('href', '/wnioski/nowy?form=800PLUS')
  })

  it('bez kodów formularza nie ma przycisku „Złóż wniosek”', () => {
    setup(item({}, { form_codes: [] }))
    expect(screen.queryByRole('link', { name: /złóż wniosek/i })).not.toBeInTheDocument()
  })

  it('maybe: pokazuje pytania tak/nie i zgłasza odpowiedź', async () => {
    const m = item({
      status: 'maybe',
      questions: [{ condition_id: 'school', text: 'Czy dziecko chodzi do szkoły?' }],
    })
    const onAnswer = setup(m)
    expect(screen.getByText('Może ci przysługiwać')).toBeInTheDocument()
    expect(screen.getByText('Czy dziecko chodzi do szkoły?')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /tak/i }))
    expect(onAnswer).toHaveBeenCalledWith('nat-800plus', 'school', true)
    await userEvent.click(screen.getByRole('button', { name: /nie/i }))
    expect(onAnswer).toHaveBeenCalledWith('nat-800plus', 'school', false)
  })

  it('no: pokazuje powód i nie oferuje wniosku', () => {
    setup(item({ status: 'no', reasons: [], unmet: ['Dostępne po urodzeniu dziecka.'] }))
    expect(screen.getByText('Nie pasuje')).toBeInTheDocument()
    expect(screen.getByText(/Dostępne po urodzeniu dziecka/)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /złóż wniosek/i })).not.toBeInTheDocument()
  })

  it('oznacza dane do weryfikacji', () => {
    setup(item({}, { verify: true }))
    expect(screen.getByText(/potwierdź w źródle/i)).toBeInTheDocument()
  })

  it('pokazuje termin, gdy jest', () => {
    const m = item()
    m.deadline_date = '2026-11-30'
    setup(m)
    expect(screen.getByText(/30\.11\.2026/)).toBeInTheDocument()
  })
})
