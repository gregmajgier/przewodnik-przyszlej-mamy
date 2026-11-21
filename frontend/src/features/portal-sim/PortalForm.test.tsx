import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import type { ReactElement } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../lib/api'
import { routeApi } from '../../test/routeApi'
import type { FromFrame, ToFrame } from './agentBridge'
import { coerceFill } from './portalSchema'
import type { PortalSchema } from './portalSchema'
import EmpatiaForm from './EmpatiaForm'
import EzusForm from './EzusForm'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

const bridge = vi.hoisted(() => ({
  toFrame: undefined as undefined | ((m: ToFrame) => void),
  posted: [] as FromFrame[],
}))
vi.mock('./agentBridge', () => ({
  listenToParent: (h: (m: ToFrame) => void) => {
    bridge.toFrame = h
    return () => {
      bridge.toFrame = undefined
    }
  },
  postToParent: (m: FromFrame) => bridge.posted.push(m),
}))

const SCHEMA: PortalSchema = {
  portal_id: 'ezus_800plus',
  title: 'eZUS — Wniosek o świadczenie wychowawcze 800+',
  kind: 'ezus',
  form_code: '800PLUS',
  fields: [
    { id: 'street', label: 'Ulica', type: 'text', required: true, choices: null },
    { id: 'citizenship', label: 'Obywatelstwo', type: 'choice', required: true, choices: ['polskie', 'inne'], default: 'polskie' },
    { id: 'birth', label: 'Data urodzenia', type: 'date', required: false, choices: null },
    { id: 'consent', label: 'Oświadczam, że dane są prawdziwe', type: 'bool', required: true, choices: null },
  ],
}

function fromAgent(msg: ToFrame) {
  act(() => bridge.toFrame?.(msg))
}

const acks = () => bridge.posted.filter((m) => m.type === 'ack')

beforeEach(() => {
  bridge.posted.length = 0
  bridge.toFrame = undefined
  routeApi({ 'GET /api/applications/portals/ezus_800plus': SCHEMA })
})

// useParams wymaga trasy — prosty wrapper z <Routes>
function renderAt(path: string, element: ReactElement, route: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path={route} element={element} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('formularz online (eZUS / Emp@tia)', () => {
  it('pokazuje nazwę portalu i pola ze schematu', async () => {
    renderAt('/sim/ezus/ezus_800plus', <EzusForm />, '/sim/ezus/:portalId')
    expect(await screen.findByText('eZUS')).toBeInTheDocument()
    expect(screen.queryByText(/symulacja/i)).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /800\+/ })).toBeInTheDocument()
    expect(screen.getByLabelText(/ulica/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/obywatelstwo/i)).toHaveValue('polskie') // wartość domyślna ze schematu
    expect(screen.getByLabelText(/oświadczam/i)).not.toBeChecked()
  })

  it('wersja Emp@tia ma własną nazwę portalu', async () => {
    routeApi({ 'GET /api/applications/portals/emp_kdr': { ...SCHEMA, portal_id: 'emp_kdr', kind: 'empatia', title: 'Emp@tia — KDR' } })
    renderAt('/sim/empatia/emp_kdr', <EmpatiaForm />, '/sim/empatia/:portalId')
    expect(await screen.findByText('Emp@tia')).toBeInTheDocument()
  })

  it('zgłasza gotowość dopiero po załadowaniu schematu', async () => {
    renderAt('/sim/ezus/ezus_800plus', <EzusForm />, '/sim/ezus/:portalId')
    expect(bridge.posted).toEqual([])
    await screen.findByLabelText(/ulica/i)
    expect(bridge.posted).toEqual([{ type: 'ready' }])
  })

  it('wypełnia pole poleceniem agenta, podświetla je i odsyła potwierdzenie z położeniem', async () => {
    renderAt('/sim/ezus/ezus_800plus', <EzusForm />, '/sim/ezus/:portalId')
    await screen.findByLabelText(/ulica/i)
    fromAgent({ type: 'fill', fieldId: 'street', value: 'Floriańska' })
    expect(screen.getByLabelText(/ulica/i)).toHaveValue('Floriańska')
    expect(screen.getByLabelText(/ulica/i).closest('.sim-field')).toHaveClass('is-agent-filled')
    await waitFor(() => expect(acks()).toHaveLength(1))
    expect(acks()[0]).toMatchObject({ type: 'ack', fieldId: 'street', ok: true, rect: expect.objectContaining({ width: expect.any(Number) }) })
  })

  it('odrzuca pole spoza schematu i wartość niezgodną z typem (nie wstrzykuje do formularza)', async () => {
    renderAt('/sim/ezus/ezus_800plus', <EzusForm />, '/sim/ezus/:portalId')
    await screen.findByLabelText(/ulica/i)
    fromAgent({ type: 'fill', fieldId: 'nie-ma-takiego', value: 'x' })
    fromAgent({ type: 'fill', fieldId: 'citizenship', value: 'marsjańskie' }) // spoza listy wyboru
    fromAgent({ type: 'fill', fieldId: 'birth', value: '1 stycznia' }) // zły format daty
    fromAgent({ type: 'fill', fieldId: 'consent', value: 'tak' }) // bool wymaga true/false
    fromAgent({ type: 'fill', fieldId: 'street', value: 'x'.repeat(501) }) // za długie
    expect(acks().map((a) => a.type === 'ack' && [a.fieldId, a.ok])).toEqual([
      ['nie-ma-takiego', false],
      ['citizenship', false],
      ['birth', false],
      ['consent', false],
      ['street', false],
    ])
    expect(screen.getByLabelText(/obywatelstwo/i)).toHaveValue('polskie')
    expect(screen.getByLabelText(/data urodzenia/i)).toHaveValue('')
    expect(screen.getByLabelText(/oświadczam/i)).not.toBeChecked()
    expect(screen.getByLabelText(/ulica/i)).toHaveValue('')
    expect(document.querySelector('.is-agent-filled')).toBeNull()
  })

  it('zgłasza zmiany wprowadzone przez rodzica', async () => {
    renderAt('/sim/ezus/ezus_800plus', <EzusForm />, '/sim/ezus/:portalId')
    await userEvent.type(await screen.findByLabelText(/ulica/i), 'A')
    expect(bridge.posted).toContainEqual({ type: 'edited', fieldId: 'street', value: 'A' })
    await userEvent.click(screen.getByLabelText(/oświadczam/i))
    expect(bridge.posted).toContainEqual({ type: 'edited', fieldId: 'consent', value: true })
  })

  it('nie wysyła wniosku z pustymi wymaganymi polami — zgłasza `invalid`', async () => {
    renderAt('/sim/ezus/ezus_800plus', <EzusForm />, '/sim/ezus/:portalId')
    await userEvent.click(await screen.findByRole('button', { name: /wyślij wniosek/i }))
    expect(bridge.posted).toContainEqual({ type: 'invalid', fieldIds: ['street', 'consent'] })
    expect(bridge.posted.some((m) => m.type === 'submitted')).toBe(false)
    expect(screen.getAllByText('To pole jest wymagane.')).toHaveLength(2)
  })

  it('polecenie `submit` od rodzica składa kompletny formularz', async () => {
    renderAt('/sim/ezus/ezus_800plus', <EzusForm />, '/sim/ezus/:portalId')
    await screen.findByLabelText(/ulica/i)
    fromAgent({ type: 'fill', fieldId: 'street', value: 'Floriańska' })
    fromAgent({ type: 'fill', fieldId: 'consent', value: true })
    fromAgent({ type: 'submit' })
    expect(bridge.posted).toContainEqual({ type: 'submitted' })
    expect(await screen.findByRole('heading', { name: /wniosek złożony/i })).toBeInTheDocument()
  })

  it('bez zalogowania prosi o logowanie, inne błędy pokazuje jako komunikat', async () => {
    routeApi({ 'GET /api/applications/portals/ezus_800plus': new ApiError(401, 'Sesja wygasła.') })
    const { unmount } = renderAt('/sim/ezus/ezus_800plus', <EzusForm />, '/sim/ezus/:portalId')
    expect(await screen.findByRole('alert')).toHaveTextContent(/zaloguj się/i)
    unmount()
    routeApi({ 'GET /api/applications/portals/ezus_800plus': new ApiError(404, 'Nie ma takiej makiety portalu.') })
    renderAt('/sim/ezus/ezus_800plus', <EzusForm />, '/sim/ezus/:portalId')
    expect(await screen.findByRole('alert')).toHaveTextContent('Nie ma takiej makiety portalu.')
  })
})

describe('coerceFill', () => {
  const f = (type: PortalSchema['fields'][number]['type'], choices: string[] | null = null) => ({ id: 'x', label: 'X', type, required: false, choices })
  it('akceptuje tylko wartości zgodne z typem pola', () => {
    expect(coerceFill(f('text'), 'abc')).toBe('abc')
    expect(coerceFill(f('text'), true)).toBeNull()
    expect(coerceFill(f('date'), '2027-01-20')).toBe('2027-01-20')
    expect(coerceFill(f('date'), '20.01.2027')).toBeNull()
    expect(coerceFill(f('bool'), false)).toBe(false)
    expect(coerceFill(f('bool'), 'true')).toBeNull()
    expect(coerceFill(f('choice', ['a', 'b']), 'b')).toBe('b')
    expect(coerceFill(f('choice', ['a', 'b']), 'c')).toBeNull()
    expect(coerceFill(f('choice'), 'a')).toBeNull() // brak listy wyboru = nic nie jest dozwolone
  })
})
