import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import { ApiError } from '../../lib/api'
import { markOnboarded } from '../../lib/onboarding'
import { NOWAK } from '../../test/fixtures'
import { ANNA, makeSession, renderWithSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import JoinPage from './JoinPage'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

describe('JoinPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('błędny kod pokazuje komunikat po polsku', async () => {
    routeApi({
      'POST /api/families/join': new ApiError(
        404,
        'Nie znaleziono rodziny o takim kodzie. Sprawdź kod i spróbuj ponownie.',
      ),
    })
    renderWithSession(<JoinPage />)
    await userEvent.type(screen.getByLabelText(/kod zaproszenia/i), 'ZZZZZZZZ')
    await userEvent.click(screen.getByRole('button', { name: /dołącz do rodziny/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/nie znaleziono rodziny o takim kodzie/i)
  })

  it('poprawny kod od razu dołącza do rodziny i odświeża sesję (bez czekania na akceptację)', async () => {
    const mocked = routeApi({
      'POST /api/families/join': { id: 'jr-1', family_id: 'f1', user_id: 'u', status: 'accepted' },
    })
    const session = makeSession()
    renderWithSession(<JoinPage />, { session })
    await userEvent.type(screen.getByLabelText(/kod zaproszenia/i), 'abcd2345')
    await userEvent.click(screen.getByRole('button', { name: /dołącz do rodziny/i }))
    await waitFor(() =>
      expect(mocked).toHaveBeenCalledWith('/api/families/join', {
        method: 'POST',
        body: { code: 'ABCD2345' }, // kod wpisujemy wielkimi literami, jak w aplikacji drugiego rodzica
      }),
    )
    await waitFor(() => expect(session.refresh).toHaveBeenCalled())
    expect(screen.queryByRole('heading', { name: /prawie gotowe/i })).not.toBeInTheDocument()
  })

  it('"Sprawdź status" wysyła kod jeszcze raz i odświeża sesję (dołącza automatycznie)', async () => {
    const mocked = routeApi({
      'POST /api/families/join': { id: 'jr-1', family_id: 'f1', user_id: 'u', status: 'pending' },
    })
    const session = makeSession()
    renderWithSession(<JoinPage />, { session })
    await userEvent.type(screen.getByLabelText(/kod zaproszenia/i), 'ABCD2345')
    await userEvent.click(screen.getByRole('button', { name: /dołącz do rodziny/i }))
    await userEvent.click(await screen.findByRole('button', { name: /sprawdź status/i }))
    await waitFor(() => expect(session.refresh).toHaveBeenCalled())
    expect(mocked.mock.calls.filter(([url]) => url === '/api/families/join')).toHaveLength(2)
  })

  it('po przyjęciu do rodziny prowadzi do dalszych kroków onboardingu, a po onboardingu do panelu', () => {
    const tree = (
      <Routes>
        <Route path="/dolacz" element={<JoinPage />} />
        <Route path="/start" element={<p>Onboarding</p>} />
        <Route path="/" element={<p>Panel</p>} />
      </Routes>
    )
    const { unmount } = renderWithSession(tree, { route: '/dolacz', session: makeSession({ family: NOWAK }) })
    expect(screen.getByText('Onboarding')).toBeInTheDocument()
    unmount()
    markOnboarded(ANNA.id)
    renderWithSession(tree, { route: '/dolacz', session: makeSession({ family: NOWAK }) })
    expect(screen.getByText('Panel')).toBeInTheDocument()
  })
})
