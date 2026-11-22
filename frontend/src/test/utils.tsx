import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import { SessionContext } from '../lib/session'
import type { SessionValue } from '../lib/session'
import type { User } from '../lib/types'

export const ANNA: User = {
  id: 'user-nowak-anna',
  role: 'parent',
  name: 'Anna Nowak',
  email: null,
  persona_id: 'persona-nowak-anna',
  family_id: null,
  unit_id: null,
}

export function makeSession(over: Partial<SessionValue> = {}): SessionValue {
  return {
    user: ANNA,
    family: null,
    token: 'tok',
    loading: false,
    login: vi.fn(async () => ({ user: ANNA, family: null })),
    loginOfficial: vi.fn(async () => ANNA),
    logout: vi.fn(),
    refresh: vi.fn(async () => {}),
    ...over,
  }
}

export function renderWithSession(
  ui: ReactElement,
  // `route` może nieść stan nawigacji (np. `{ pathname: '/rodzina', state: { hardSituation: true } }`)
  { session = makeSession(), route = '/' }: { session?: SessionValue; route?: string | { pathname: string; state?: unknown } } = {},
) {
  return {
    session,
    ...render(
      <SessionContext.Provider value={session}>
        <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
      </SessionContext.Provider>,
    ),
  }
}
