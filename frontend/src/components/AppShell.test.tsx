import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { NOWAK } from '../test/fixtures'
import { makeSession, renderWithSession } from '../test/utils'
import { AppShell } from './AppShell'

vi.mock('../lib/api', async (orig) => ({
  ...(await orig<typeof import('../lib/api')>()),
  api: vi.fn(async (path: string) => (path.startsWith('/api/notifications') ? [] : { mode: 'normal' })),
}))

function Tree() {
  return (
    <Routes>
      <Route path="/logowanie" element={<p>Strona logowania</p>} />
      <Route path="/start" element={<p>Onboarding</p>} />
      <Route element={<AppShell />}>
        <Route path="/sekret" element={<p>Treść chroniona</p>} />
      </Route>
    </Routes>
  )
}

describe('AppShell', () => {
  it('bez sesji przekierowuje na /logowanie', () => {
    renderWithSession(<Tree />, { route: '/sekret', session: makeSession({ user: null, token: null }) })
    expect(screen.getByText('Strona logowania')).toBeInTheDocument()
    expect(screen.queryByText('Treść chroniona')).not.toBeInTheDocument()
  })

  it('w trakcie odtwarzania sesji pokazuje ekran ładowania, bez przekierowania', () => {
    renderWithSession(<Tree />, { route: '/sekret', session: makeSession({ user: null, token: 'tok', loading: true }) })
    expect(screen.getByRole('status')).toHaveTextContent(/ładuję/i)
    expect(screen.queryByText('Strona logowania')).not.toBeInTheDocument()
  })

  it('bez rodziny kieruje do onboardingu (panel jest aktywny dopiero po konfiguracji)', () => {
    renderWithSession(<Tree />, { route: '/sekret', session: makeSession({ family: null }) })
    expect(screen.getByText('Onboarding')).toBeInTheDocument()
  })

  it('nagłówek bez nawigacji: menu konta prowadzi do Rodziny i danych, z wylogowaniem; jest przycisk „Zapytaj”', async () => {
    const session = makeSession({ family: NOWAK })
    renderWithSession(<Tree />, { route: '/sekret', session })
    expect(screen.getByText('Treść chroniona')).toBeInTheDocument()
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /zapytaj mrodzinę/i })).toHaveAttribute('href', '/czat')

    await userEvent.click(screen.getByRole('button', { name: /konto: anna nowak/i }))
    expect(screen.getByRole('menuitem', { name: 'Rodzina' })).toHaveAttribute('href', '/rodzina')
    expect(screen.getByRole('menuitem', { name: 'Moje dane' })).toHaveAttribute('href', '/dane')
    await userEvent.click(screen.getByRole('menuitem', { name: /wyloguj/i }))
    expect(session.logout).toHaveBeenCalled()
  })
})
