import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { DateField } from './controls'

function Harness({ initial = '' }: { initial?: string }) {
  const [value, setValue] = useState(initial)
  return (
    <>
      <DateField label="Przewidywany termin porodu" value={value} onChange={setValue} />
      <output data-testid="iso">{value}</output>
      <p>poza polem</p>
    </>
  )
}

describe('DateField — mini kalendarz', () => {
  it('kliknięcie w pole otwiera kalendarz, a wybór dnia wpisuje datę i zamyka go', async () => {
    const user = userEvent.setup()
    render(<Harness initial="2027-01-10" />)
    await user.click(screen.getByLabelText('Przewidywany termin porodu'))
    const cal = screen.getByRole('dialog', { name: /Kalendarz: Przewidywany termin porodu/ })
    expect(cal).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Miesiąc' })).toHaveValue('0')
    await user.click(screen.getByRole('button', { name: '21 stycznia 2027' }))
    expect(screen.getByTestId('iso')).toHaveTextContent('2027-01-21')
    expect(screen.getByLabelText('Przewidywany termin porodu')).toHaveValue('21.01.2027')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('przycisk otwiera i zamyka kalendarz', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(screen.getByRole('button', { name: 'Otwórz kalendarz' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Zamknij kalendarz' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('zamyka się przyciskiem „Zamknij”, klawiszem Escape i kliknięciem obok', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const input = screen.getByLabelText('Przewidywany termin porodu')
    await user.click(input)
    await user.click(screen.getByRole('button', { name: 'Zamknij' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    await user.click(input)
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    await user.click(input)
    fireEvent.mouseDown(screen.getByText('poza polem'))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('zmiana miesiąca strzałkami i wybór roku z listy', async () => {
    const user = userEvent.setup()
    render(<Harness initial="2027-01-10" />)
    await user.click(screen.getByRole('button', { name: 'Otwórz kalendarz' }))
    await user.click(screen.getByRole('button', { name: 'Poprzedni miesiąc' }))
    expect(screen.getByRole('combobox', { name: 'Miesiąc' })).toHaveValue('11')
    expect(screen.getByRole('combobox', { name: 'Rok' })).toHaveValue('2026')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Rok' }), '2019')
    await user.click(screen.getByRole('button', { name: '26 grudnia 2019' }))
    expect(screen.getByTestId('iso')).toHaveTextContent('2019-12-26')
  })

  it('wpisywanie z klawiatury nadal działa', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.type(screen.getByLabelText('Przewidywany termin porodu'), '21012027')
    expect(screen.getByTestId('iso')).toHaveTextContent('2027-01-21')
  })
})
