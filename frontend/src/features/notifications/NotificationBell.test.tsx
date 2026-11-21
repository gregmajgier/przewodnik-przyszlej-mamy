import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { FamilyView } from '../../lib/types'
import { makeSession, renderWithSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import NotificationBell from './NotificationBell'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

const FAMILY = { family: { id: 'f' }, members: [], children: [], pending_requests: [] } as unknown as FamilyView
const N = (id: string, read: boolean) => ({
  id, kind: 'status_change', text: `Wniosek ${id}: otrzymano.`, link: '/poczta', created_at: '2026-11-21T10:00:00Z', read,
})

describe('NotificationBell', () => {
  beforeEach(() => vi.clearAllMocks())

  it('pokazuje licznik nieprzeczytanych', async () => {
    routeApi({ 'GET /api/notifications': [N('a', false), N('b', false), N('c', true)] })
    renderWithSession(<NotificationBell />, { session: makeSession({ family: FAMILY }) })
    expect(await screen.findByRole('button', { name: 'Powiadomienia: 2 nieprzeczytane' })).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('kliknięcie powiadomienia oznacza je jako przeczytane', async () => {
    const api = routeApi({ 'GET /api/notifications': [N('a', false)], 'POST /api/notifications/a/read': N('a', true) })
    renderWithSession(<NotificationBell />, { session: makeSession({ family: FAMILY }) })
    await userEvent.click(await screen.findByRole('button', { name: /Powiadomienia: 1/ }))
    await userEvent.click(screen.getByRole('link', { name: 'Wniosek a: otrzymano.' }))
    await waitFor(() => expect(api).toHaveBeenCalledWith('/api/notifications/a/read', { method: 'POST' }))
    expect(screen.getByRole('button', { name: 'Powiadomienia' })).toBeInTheDocument()
  })

  it('bez rodziny nic nie renderuje', () => {
    routeApi({})
    const { container } = renderWithSession(<NotificationBell />)
    expect(container).toBeEmptyDOMElement()
  })
})
