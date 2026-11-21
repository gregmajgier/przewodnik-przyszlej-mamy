import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Child } from '../../lib/types'
import { ChildTimeline } from './ChildTimeline'

const TODAY = new Date(2026, 10, 21)
const MAJA: Child = {
  id: 'c-maja', family_id: 'f1', name: 'Maja', birth_date: '2019-08-25', due_date: null, status: 'born', pesel: null,
  has_disability: false, foster: false, situation: null, situation_kind: null, situation_at: null, serious_illness: false,
}

describe('ChildTimeline', () => {
  it('pokazuje to, co było, etap teraz z pilną sprawą i najbliższe kroki z odliczaniem', () => {
    render(<ChildTimeline child={MAJA} tone="mint" urgent="Dobry Start: zostało 9 dni" today={TODAY} />)
    const list = screen.getByRole('list')
    const items = within(list).getAllByRole('listitem')
    expect(items).toHaveLength(2 + 1 + 4)
    const now = items.find((li) => li.getAttribute('aria-current') === 'step')!
    expect(now).toHaveTextContent('Teraz')
    expect(now).toHaveTextContent('7 lat · 1. klasa')
    expect(now).toHaveTextContent('Dobry Start: zostało 9 dni')
    expect(items[0]).toHaveTextContent('Zapisy do 1. klasy')
    expect(items[3]).toHaveTextContent('Dobry Start — nabór wniosków')
    expect(items[3]).toHaveTextContent('1 lipca 2027')
    expect(items[3]).toHaveTextContent('za 7 miesięcy')
  })

  it('rozwija całą oś czasu i zwija ją z powrotem', async () => {
    render(<ChildTimeline child={MAJA} tone="mint" today={TODAY} />)
    const button = screen.getByRole('button', { name: /pokaż całą oś czasu/i })
    expect(button).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(button)
    expect(button).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Narodziny')).toBeInTheDocument()
    expect(screen.getByText('Matura')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /zwiń oś czasu/i }))
    expect(screen.queryByText('Narodziny')).not.toBeInTheDocument()
  })

  it('dziecko w drodze: od razu „Teraz”, bez przeszłości', () => {
    render(<ChildTimeline child={{ ...MAJA, birth_date: null, due_date: '2027-01-20', status: 'expected' }} tone="sky" today={TODAY} />)
    const items = within(screen.getByRole('list')).getAllByRole('listitem')
    expect(items[0]).toHaveAttribute('aria-current', 'step')
    expect(items[0]).toHaveTextContent('W drodze · termin 20.01.2027')
    expect(items[1]).toHaveTextContent('Narodziny')
    expect(items[1]).toHaveTextContent('za 2 miesiące')
  })
})
