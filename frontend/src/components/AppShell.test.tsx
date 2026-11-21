import { screen } from '@testing-library/react'
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
})
