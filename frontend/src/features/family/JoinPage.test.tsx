import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../lib/api'
import { makeSession, renderWithSession } from '../../test/utils'
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
    await userEvent.click(screen.getByRole('button', { name: /wyślij prośbę/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/nie znaleziono rodziny o takim kodzie/i)
  })

  it('poprawny kod wysyła prośbę i pokazuje oczekiwanie na akceptację', async () => {
    const mocked = routeApi({
      'POST /api/families/join': { id: 'jr-1', family_id: 'f1', user_id: 'u', status: 'pending' },
    })
    renderWithSession(<JoinPage />)
    await userEvent.type(screen.getByLabelText(/kod zaproszenia/i), 'abcd2345')
    await userEvent.click(screen.getByRole('button', { name: /wyślij prośbę/i }))
    await waitFor(() =>
      expect(mocked).toHaveBeenCalledWith('/api/families/join', {
        method: 'POST',
        body: { code: 'ABCD2345' }, // kod wpisujemy wielkimi literami, jak w aplikacji drugiego rodzica
      }),
    )
    expect(await screen.findByRole('heading', { name: /prośba wysłana/i })).toBeInTheDocument()
  })

  it('"Sprawdź status" odświeża sesję', async () => {
    routeApi({
      'POST /api/families/join': { id: 'jr-1', family_id: 'f1', user_id: 'u', status: 'pending' },
    })
    const session = makeSession()
    renderWithSession(<JoinPage />, { session })
    await userEvent.type(screen.getByLabelText(/kod zaproszenia/i), 'ABCD2345')
    await userEvent.click(screen.getByRole('button', { name: /wyślij prośbę/i }))
    await userEvent.click(await screen.findByRole('button', { name: /sprawdź status/i }))
    expect(session.refresh).toHaveBeenCalled()
  })
})
