import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { makeSession, renderWithSession } from '../test/utils'
import { AppShell } from './AppShell'

function Tree() {
  return (
    <Routes>
      <Route path="/logowanie" element={<p>Strona logowania</p>} />
      <Route element={<AppShell />}>
        <Route path="/sekret" element={<p>Treść chroniona</p>} />
        <Route path="*" element={<p>Inna strona</p>} />
      </Route>
    </Routes>
  )
}

describe('AppShell', () => {
  it('bez sesji przekierowuje na /logowanie', () => {
    renderWithSession(<Tree />, {
      route: '/sekret',
      session: makeSession({ user: null, token: null }),
    })
    expect(screen.getByText('Strona logowania')).toBeInTheDocument()
    expect(screen.queryByText('Treść chroniona')).not.toBeInTheDocument()
  })

  it('w trakcie odtwarzania sesji nie przekierowuje, tylko czeka', () => {
    renderWithSession(<Tree />, {
      route: '/sekret',
      session: makeSession({ user: null, token: 'tok', loading: true }),
    })
    expect(screen.getByText(/ładowanie/i)).toBeInTheDocument()
    expect(screen.queryByText('Strona logowania')).not.toBeInTheDocument()
  })

  it('z sesją renderuje nawigację rodzica, treść i wylogowanie', async () => {
    const session = makeSession()
    renderWithSession(<Tree />, { route: '/sekret', session })
    expect(screen.getByText('Treść chroniona')).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: /główna/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Rodzina' })).toHaveAttribute('href', '/rodzina')
    expect(screen.getByRole('link', { name: 'Moje dane' })).toHaveAttribute('href', '/dane')
    await userEvent.click(screen.getByRole('button', { name: /wyloguj/i }))
    expect(session.logout).toHaveBeenCalled()
  })

  it('na telefonie główne zakładki są w dolnym pasku, reszta pod „Więcej”', async () => {
    renderWithSession(<Tree />, { route: '/sekret', session: makeSession() })
    const nav = screen.getByRole('navigation', { name: /główna/i })
    const bar = nav.querySelector('.nav-bar') as HTMLElement
    const sheet = nav.querySelector('.nav-sheet') as HTMLElement
    // zakładki podstawowe (Panel, Świadczenia, Wnioski, Czat) w pasku; Rodzina, Moje dane itd. w rozwijanym arkuszu
    for (const label of ['Panel', 'Świadczenia', 'Wnioski', 'Czat']) expect(within(bar).getByRole('link', { name: label })).toBeInTheDocument()
    for (const label of ['Rodzina', 'Moje dane']) expect(within(sheet).getByRole('link', { name: label })).toBeInTheDocument()
    expect(within(bar).queryByRole('link', { name: 'Rodzina' })).not.toBeInTheDocument()

    const more = within(bar).getByRole('button', { name: 'Więcej' })
    expect(more).toHaveAttribute('aria-expanded', 'false')
    expect(sheet).not.toHaveClass('is-open')
    await userEvent.click(more)
    expect(more).toHaveAttribute('aria-expanded', 'true')
    expect(sheet).toHaveClass('is-open')
    await userEvent.click(within(sheet).getByRole('link', { name: 'Moje dane' }))
    expect(sheet).not.toHaveClass('is-open') // po przejściu na inną stronę arkusz się zamyka
  })

  it('nagłówek ma tylko logo i wylogowanie, bez dziesięciu linków', () => {
    renderWithSession(<Tree />, { route: '/sekret', session: makeSession() })
    const header = document.querySelector('.shell-header') as HTMLElement
    expect(within(header).getAllByRole('link', { name: /mRodzina/ })).toHaveLength(1)
    expect(within(header).getByRole('button', { name: /wyloguj/i })).toBeInTheDocument()
  })
})
