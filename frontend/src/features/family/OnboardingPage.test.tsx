import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { FamilyView, ParentProfile } from '../../lib/types'
import { ANNA, makeSession, renderWithSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import OnboardingPage from './OnboardingPage'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

const PROFILE = {
  user_id: ANNA.id,
  known_children: [
    { name: 'Maja', birth_date: '2019-05-01', due_date: null },
    { name: 'Dziecko w drodze', birth_date: null, due_date: '2027-01-20' },
  ],
} as ParentProfile

const FAMILY_VIEW = {
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
} as FamilyView

function Tree() {
  return (
    <Routes>
      <Route path="/start" element={<OnboardingPage />} />
      <Route path="/" element={<p>Strona główna</p>} />
      <Route path="/rodzina" element={<p>Strona rodziny</p>} />
      <Route path="/dolacz" element={<p>Strona dołączania</p>} />
    </Routes>
  )
}

describe('OnboardingPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('krok 1: bez rodziny można założyć rodzinę albo dołączyć', async () => {
    const mocked = routeApi({
      'POST /api/families': FAMILY_VIEW,
      'GET /api/profile/me': PROFILE,
    })
    const session = makeSession()
    renderWithSession(<Tree />, { route: '/start', session })
    expect(screen.getByRole('link', { name: /dołącz do rodziny/i })).toHaveAttribute('href', '/dolacz')
    await userEvent.click(screen.getByRole('button', { name: /załóż rodzinę/i }))
    await waitFor(() => expect(mocked).toHaveBeenCalledWith('/api/families', { method: 'POST', body: {} }))
    expect(session.refresh).toHaveBeenCalled()
    expect(await screen.findByRole('heading', { name: /dzieci/i })).toBeInTheDocument()
  })

  it('krok 2: dzieci prefilowane z known_children, zatwierdzenie zapisuje wybrane', async () => {
    const mocked = routeApi({
      'GET /api/profile/me': PROFILE,
      'POST /api/families/me/children': { id: 'c1' },
    })
    renderWithSession(<Tree />, {
      route: '/start',
      session: makeSession({ family: FAMILY_VIEW }),
    })
    expect(await screen.findByLabelText(/Maja/)).toBeChecked()
    const drodze = screen.getByLabelText(/Dziecko w drodze/)
    expect(drodze).toBeChecked()
    await userEvent.click(screen.getByLabelText(/Maja/)) // odznacz Maję
    await userEvent.click(screen.getByRole('button', { name: /zatwierdź dzieci/i }))
    await waitFor(() =>
      expect(mocked).toHaveBeenCalledWith('/api/families/me/children', {
        method: 'POST',
        body: { name: 'Dziecko w drodze', birth_date: null, due_date: '2027-01-20' },
      }),
    )
    expect(mocked).not.toHaveBeenCalledWith(
      '/api/families/me/children',
      expect.objectContaining({ body: expect.objectContaining({ name: 'Maja' }) }),
    )
    expect(await screen.findByRole('heading', { name: /drugi rodzic/i })).toBeInTheDocument()
  })

  it('krok 3: pokazuje kod i pozwala pominąć drugiego rodzica', async () => {
    routeApi({
      'GET /api/profile/me': { ...PROFILE, known_children: [] },
    })
    renderWithSession(<Tree />, {
      route: '/start',
      session: makeSession({ family: FAMILY_VIEW }),
    })
    // brak znanych dzieci => krok 2 pomija się od razu
    expect(await screen.findByText('ABCD2345')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /wychowuję dziecko samodzielnie/i }))
    expect(await screen.findByText('Strona główna')).toBeInTheDocument()
  })
})
