import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { FamilyView } from '../../lib/types'
import { ANNA, makeSession, renderWithSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import FamilyPage from './FamilyPage'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

const PIOTR = { ...ANNA, id: 'user-nowak-piotr', name: 'Piotr Nowak' }

function view(over: Partial<FamilyView> = {}): FamilyView {
  return {
    family: {
      id: 'f1',
      name: 'Rodzina Nowak',
      owner_id: ANNA.id,
      member_ids: [ANNA.id],
      invite_code: 'ABCD2345',
      invite_expires_at: null,
    },
    members: [ANNA],
    children: [],
    pending_requests: [],
    ...over,
  }
}

describe('FamilyPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('pokazuje prośbę pending i wywołuje accept', async () => {
    const pending = view({
      pending_requests: [
        { id: 'jr-1', family_id: 'f1', user_id: PIOTR.id, status: 'pending', user_name: 'Piotr Nowak' },
      ],
    })
    const accepted = view({
      family: { ...pending.family, member_ids: [ANNA.id, PIOTR.id] },
      members: [ANNA, PIOTR],
    })
    let current = pending
    const mocked = routeApi({
      'GET /api/families/me': () => current,
      'POST /api/families/me/join-requests/jr-1/accept': () => {
        current = accepted
        return accepted
      },
    })
    const session = makeSession()
    renderWithSession(<FamilyPage />, { session })
    expect(await screen.findByText(/chce dołączyć/i)).toBeInTheDocument()
    expect(screen.getByText('Piotr Nowak')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /akceptuj/i }))
    await waitFor(() =>
      expect(mocked).toHaveBeenCalledWith('/api/families/me/join-requests/jr-1/accept', {
        method: 'POST',
      }),
    )
    await waitFor(() => expect(screen.queryByText(/chce dołączyć/i)).not.toBeInTheDocument())
    expect(session.refresh).toHaveBeenCalled()
  })

  it('odrzucenie wywołuje reject', async () => {
    const pending = view({
      pending_requests: [
        { id: 'jr-1', family_id: 'f1', user_id: PIOTR.id, status: 'pending', user_name: 'Piotr Nowak' },
      ],
    })
    const mocked = routeApi({
      'GET /api/families/me': pending,
      'POST /api/families/me/join-requests/jr-1/reject': view(),
    })
    renderWithSession(<FamilyPage />)
    await userEvent.click(await screen.findByRole('button', { name: /odrzuć/i }))
    expect(mocked).toHaveBeenCalledWith('/api/families/me/join-requests/jr-1/reject', {
      method: 'POST',
    })
  })

  it('pokazuje członków, kod zaproszenia i dzieci (w tym dziecko w drodze)', async () => {
    routeApi({
      'GET /api/families/me': view({
        children: [
          {
            id: 'c1',
            family_id: 'f1',
            name: 'Maja',
            birth_date: '2019-05-01',
            due_date: null,
            status: 'born',
          } as never,
          {
            id: 'c2',
            family_id: 'f1',
            name: 'Maluszek',
            birth_date: null,
            due_date: '2027-01-20',
            status: 'expected',
          } as never,
        ],
      }),
    })
    renderWithSession(<FamilyPage />)
    expect(await screen.findByText('ABCD2345')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Maja' })).toBeInTheDocument()
    expect(screen.getByText(/w drodze · termin 20\.01\.2027/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Anna Nowak/ })).toHaveAttribute('href', `/sprawy/${ANNA.id}`)
  })

  it('błąd pobrania rodziny pokazuje komunikat', async () => {
    const { ApiError } = await import('../../lib/api')
    routeApi({ 'GET /api/families/me': new ApiError(500, 'Coś poszło nie tak po naszej stronie.') })
    renderWithSession(<FamilyPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/coś poszło nie tak/i)
  })

  it('dodanie dziecka w arkuszu: imię, „w drodze”, termin w formacie DD.MM.RRRR', async () => {
    const mocked = routeApi({ 'GET /api/families/me': view(), 'POST /api/families/me/children': { id: 'c9' } })
    renderWithSession(<FamilyPage />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: /dodaj dziecko/i }))
    const sheet = await screen.findByRole('dialog', { name: /dodaj dziecko/i })
    await new Promise((r) => setTimeout(r, 50)) // arkusz ustawia fokus na pierwszym polu
    await user.click(within(sheet).getByRole('tab', { name: /w drodze/i }))
    await user.type(within(sheet).getByLabelText('Imię'), 'Zosia')
    await user.type(within(sheet).getByLabelText(/termin porodu/i), '20012027')
    const save = within(sheet).getByRole('button', { name: /^dodaj dziecko$/i })
    await waitFor(() => expect(save).toBeEnabled())
    await user.click(save)
    await waitFor(() =>
      expect(mocked).toHaveBeenCalledWith('/api/families/me/children', {
        method: 'POST',
        body: { name: 'Zosia', birth_date: null, due_date: '2027-01-20' },
      }),
    )
  })
})
