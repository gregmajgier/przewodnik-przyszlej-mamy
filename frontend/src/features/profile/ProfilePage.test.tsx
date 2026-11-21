import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { MemberProfile } from '../../lib/types'
import { renderWithSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import ProfilePage from './ProfilePage'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

const ANNA_PROFILE: MemberProfile = {
  user_id: 'user-nowak-anna',
  user_name: 'Anna Nowak',
  first_name: 'Anna',
  last_name: 'Nowak',
  pesel: '95031512345',
  birth_date: '1995-03-15',
  address: {
    city: 'Kraków',
    gmina: 'Kraków',
    powiat: 'Kraków',
    voivodeship: 'Małopolskie',
    postal_code: '30-001',
  },
  insurance: [
    {
      kind: 'employment',
      payer: 'Krakowskie Centrum Usług Wspólnych Sp. z o.o.',
      contribution_base: 7850,
      voluntary_sickness: null,
      since: '2021-11-21',
    },
  ],
  ezla: [{ code: 'B', from_date: '2026-11-14', to_date: '2026-12-12' }],
  contribution_debt: null,
  known_children: [{ name: 'Maja', birth_date: '2019-05-01', due_date: null }],
  answers: { foster: false },
}

describe('ProfilePage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('pokazuje dane obojga rodziców z podziałem na źródła', async () => {
    routeApi({
      'GET /api/profile': {
        members: [
          ANNA_PROFILE,
          {
            ...ANNA_PROFILE,
            user_id: 'user-nowak-piotr',
            user_name: 'Piotr Nowak',
            first_name: 'Piotr',
            pesel: '92010112345',
            ezla: [],
            insurance: [{ ...ANNA_PROFILE.insurance[0], payer: 'Małopolska Hurtownia Budowlana S.A.' }],
          },
        ],
      },
    })
    renderWithSession(<ProfilePage />)
    expect(await screen.findByRole('heading', { name: 'Anna Nowak' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Piotr Nowak' })).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { name: /ZUS i mObywatel/i })).toHaveLength(2)
    expect(screen.getAllByRole('heading', { name: /umowy o pracę/i })).toHaveLength(2)
    expect(screen.getAllByRole('heading', { name: /twoje odpowiedzi/i })).toHaveLength(2)
    expect(screen.getByText(/Krakowskie Centrum Usług Wspólnych/)).toBeInTheDocument()
    expect(screen.getByText(/Małopolska Hurtownia Budowlana/)).toBeInTheDocument()
    expect(screen.getByText(/e-ZLA/)).toBeInTheDocument()
  })

  it('maskuje PESEL (widoczne tylko ostatnie 4 cyfry)', async () => {
    routeApi({ 'GET /api/profile': { members: [ANNA_PROFILE] } })
    renderWithSession(<ProfilePage />)
    await screen.findByRole('heading', { name: 'Anna Nowak' })
    expect(screen.queryByText('95031512345')).not.toBeInTheDocument()
    expect(screen.getByText(/•+2345/)).toBeInTheDocument()
  })

  it('podpisuje źródło danych (ZUS i mObywatel), bez etykiet „symulacja”', async () => {
    routeApi({ 'GET /api/profile': { members: [ANNA_PROFILE] } })
    renderWithSession(<ProfilePage />)
    expect(await screen.findByText(/dane z ZUS i mObywatela/i)).toBeInTheDocument()
    expect(screen.queryByText(/symulacja/i)).not.toBeInTheDocument()
  })
})
