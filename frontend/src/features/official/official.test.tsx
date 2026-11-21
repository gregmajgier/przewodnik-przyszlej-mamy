import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../lib/api'
import { SessionContext } from '../../lib/session'
import type { User } from '../../lib/types'
import { makeSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import BenefitEditor from './BenefitEditor'
import OfficialLayout from './OfficialLayout'
import OfficialLogin from './OfficialLogin'
import type { OfficialBenefit } from './types'
import { EMPTY_CRITERIA } from './types'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

const OFFICIAL: User = {
  id: 'official-krakow',
  role: 'official',
  name: 'Urzędnik Gminy Kraków',
  email: 'urzednik.krakow@mrodzina.local',
  persona_id: null,
  family_id: null,
  unit_id: 'unit-krakow',
}

const BENEFIT: OfficialBenefit = {
  id: 'b1',
  name: 'Dopłata do żłobka',
  scope: 'municipal',
  unit_id: 'unit-krakow',
  category: 'benefit',
  description: 'Opis',
  amount_text: '500 zł',
  annual_value_estimate: null,
  deadline_text: null,
  how_to_apply: '',
  apply_url: null,
  source_url: '',
  criteria: EMPTY_CRITERIA,
  extra_conditions: [],
  extra_text: 'Zameldowanie w gminie od 12 miesięcy.',
  status: 'draft',
  conditions_approved: false,
  updated_at: null,
}

const EXTRACTED: OfficialBenefit = {
  ...BENEFIT,
  status: 'awaiting_approval',
  extra_conditions: [
    { id: 'zameldowanie', text: 'Zameldowanie w gminie od 12 miesięcy', kind: 'ask', question: 'Czy jesteś zameldowana od 12 miesięcy?', profile_key: null },
    { id: 'zlobek', text: 'Dziecko w publicznym żłobku', kind: 'auto', question: 'Czy dziecko chodzi do żłobka?', profile_key: 'child_in_public_nursery' },
  ],
}

function renderEditor(user: User = OFFICIAL) {
  return render(
    <SessionContext.Provider value={makeSession({ user })}>
      <MemoryRouter initialEntries={['/urzednik/swiadczenia/b1']}>
        <Routes>
          <Route path="/urzednik/swiadczenia/:id" element={<BenefitEditor />} />
        </Routes>
      </MemoryRouter>
    </SessionContext.Provider>,
  )
}

describe('Panel urzędnika', () => {
  beforeEach(() => vi.clearAllMocks())

  it('logowanie urzędnika wywołuje loginOfficial i przechodzi do panelu', async () => {
    const session = makeSession({ user: null, loginOfficial: vi.fn(async () => OFFICIAL) })
    render(
      <SessionContext.Provider value={session}>
        <MemoryRouter initialEntries={['/urzednik/logowanie']}>
          <Routes>
            <Route path="/urzednik/logowanie" element={<OfficialLogin />} />
            <Route path="/urzednik" element={<p>PANEL</p>} />
          </Routes>
        </MemoryRouter>
      </SessionContext.Provider>,
    )
    await userEvent.type(screen.getByLabelText('E-mail służbowy'), 'urzednik.krakow@mrodzina.local')
    await userEvent.type(screen.getByLabelText('Hasło'), 'demo1234')
    await userEvent.click(screen.getByRole('button', { name: 'Zaloguj się' }))
    expect(session.loginOfficial).toHaveBeenCalledWith('urzednik.krakow@mrodzina.local', 'demo1234')
    expect(await screen.findByText('PANEL')).toBeInTheDocument()
  })

  it('błędne hasło pokazuje komunikat', async () => {
    const session = makeSession({
      user: null,
      loginOfficial: vi.fn(async () => {
        throw new ApiError(401, 'x')
      }),
    })
    render(
      <SessionContext.Provider value={session}>
        <MemoryRouter>
          <OfficialLogin />
        </MemoryRouter>
      </SessionContext.Provider>,
    )
    await userEvent.type(screen.getByLabelText('E-mail służbowy'), 'a@b.pl')
    await userEvent.type(screen.getByLabelText('Hasło'), 'zle')
    await userEvent.click(screen.getByRole('button', { name: 'Zaloguj się' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Nieprawidłowy e-mail lub hasło')
  })

  it('rodzic w panelu jest przekierowany do logowania urzędnika', () => {
    render(
      <SessionContext.Provider value={makeSession()}>
        <MemoryRouter initialEntries={['/urzednik']}>
          <Routes>
            <Route path="/urzednik" element={<OfficialLayout />} />
            <Route path="/urzednik/logowanie" element={<p>LOGOWANIE</p>} />
          </Routes>
        </MemoryRouter>
      </SessionContext.Provider>,
    )
    expect(screen.getByText('LOGOWANIE')).toBeInTheDocument()
  })

  it('edytor blokuje publikację do zatwierdzenia warunków', async () => {
    const api = routeApi({
      'GET /api/official/benefits/b1': BENEFIT,
      'POST /api/official/benefits/b1/extract-conditions': EXTRACTED,
      'POST /api/official/benefits/b1/approve-conditions': (init?: { body?: unknown }) => ({
        ...EXTRACTED,
        extra_conditions: (init?.body as { conditions: unknown[] } | undefined)?.conditions ?? [],
        conditions_approved: true,
      }),
      'POST /api/official/benefits/b1/publish': { ...EXTRACTED, conditions_approved: true, status: 'published' },
    })
    renderEditor()
    const publish = await screen.findByRole('button', { name: 'Opublikuj' })
    expect(publish).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Wyodrębnij warunki' }))
    expect(await screen.findByDisplayValue('Dziecko w publicznym żłobku')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Opublikuj' })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Zatwierdź warunki' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Opublikuj' })).toBeEnabled())
    await userEvent.click(screen.getByRole('button', { name: 'Opublikuj' }))
    await waitFor(() => expect(api.mock.calls.some(([p]) => p === '/api/official/benefits/b1/publish')).toBe(true))
  })

  it('wyodrębnione warunki można edytować i usuwać przed zatwierdzeniem', async () => {
    const api = routeApi({
      'GET /api/official/benefits/b1': EXTRACTED,
      'POST /api/official/benefits/b1/approve-conditions': { ...EXTRACTED, conditions_approved: true },
    })
    renderEditor()
    const first = await screen.findByLabelText('Warunek 1')
    fireEvent.change(first, { target: { value: 'Zameldowanie w Krakowie od 12 miesięcy' } })
    await userEvent.click(screen.getByRole('button', { name: 'Usuń warunek 2' }))
    expect(screen.queryByDisplayValue('Dziecko w publicznym żłobku')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Zatwierdź warunki' }))
    const call = api.mock.calls.find(([p]) => p === '/api/official/benefits/b1/approve-conditions')
    const sent = (call?.[1]?.body ?? { conditions: [] }) as { conditions: { text: string }[] }
    expect(sent.conditions.map((c) => c.text)).toEqual(['Zameldowanie w Krakowie od 12 miesięcy'])
  })

  it('błąd AI pokazuje komunikat i pozwala dodać warunek ręcznie', async () => {
    routeApi({
      'GET /api/official/benefits/b1': BENEFIT,
      'POST /api/official/benefits/b1/extract-conditions': new ApiError(502, 'Nie udało się wyodrębnić warunków — dodaj je ręcznie.'),
    })
    renderEditor()
    await userEvent.click(await screen.findByRole('button', { name: 'Wyodrębnij warunki' }))
    expect(await screen.findByText(/dodaj je ręcznie/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Dodaj warunek ręcznie' }))
    expect(screen.getByLabelText('Warunek 1')).toBeInTheDocument()
  })
})
