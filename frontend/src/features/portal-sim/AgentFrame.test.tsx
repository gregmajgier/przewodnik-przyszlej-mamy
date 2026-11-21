import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../lib/api'
import { routeApi } from '../../test/routeApi'
import type { AgentPlan, Application } from '../applications/types'
import type { FromFrame, ToFrame } from './agentBridge'
import AgentFrame from './AgentFrame'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

// Atrapa mostu: zamiast prawdziwego <iframe> i postMessage — wiadomości wysyłamy i odbieramy ręcznie.
const bridge = vi.hoisted(() => ({
  handlers: new Set<(m: FromFrame) => void>(),
  posted: [] as ToFrame[],
  autoAck: true,
  refuse: new Set<string>(),
}))
vi.mock('./agentBridge', () => ({
  listenFromFrame: (h: (m: FromFrame) => void) => {
    bridge.handlers.add(h)
    return () => bridge.handlers.delete(h)
  },
  postToFrame: (_win: unknown, msg: ToFrame) => {
    bridge.posted.push(msg)
    if (msg.type === 'fill' && bridge.autoAck) {
      queueMicrotask(() =>
        emit({ type: 'ack', fieldId: msg.fieldId, ok: !bridge.refuse.has(msg.fieldId), rect: { x: 10, y: 20, width: 100, height: 20 } }),
      )
    }
  },
}))

function emit(msg: FromFrame) {
  act(() => bridge.handlers.forEach((h) => h(msg)))
}

const fills = () => bridge.posted.filter((m) => m.type === 'fill').map((m) => (m as Extract<ToFrame, { type: 'fill' }>).fieldId)

const PLAN: AgentPlan = {
  application_id: 'app-1',
  portal_id: 'ezus_800plus',
  title: 'eZUS — 800+',
  kind: 'ezus',
  steps: [
    { field_id: 'applicant_first_name', label: 'Imię wnioskodawcy', value: 'Anna', reason: 'Z profilu ZUS.' },
    { field_id: 'street', label: 'Ulica', value: 'Floriańska', reason: 'Adres z profilu.' },
    { field_id: 'consent', label: 'Oświadczenie', value: true, reason: 'Wymagane.' },
  ],
  blocked: [],
}
const BLOCKED_PLAN: AgentPlan = {
  ...PLAN,
  steps: PLAN.steps.slice(0, 2),
  blocked: [{ field_id: 'child_pesel', label: 'PESEL dziecka', type: 'text', choices: null }],
}
const SENT = { id: 'app-1', status: 'sent' } as Application

function reduceMotion() {
  vi.stubGlobal('matchMedia', vi.fn((q: string) => ({ matches: q.includes('reduce'), media: q, addEventListener: vi.fn(), removeEventListener: vi.fn() })))
}

beforeEach(() => {
  vi.unstubAllGlobals()
  reduceMotion() // bez pauz między krokami — testy działają na prawdziwych timerach
  bridge.handlers.clear()
  bridge.posted.length = 0
  bridge.autoAck = true
  bridge.refuse.clear()
})

function setup(plans: AgentPlan[] = [PLAN], extra: Record<string, unknown> = {}) {
  let n = 0
  const mocked = routeApi({
    'POST /api/applications/app-1/agent-plan': () => plans[Math.min(n++, plans.length - 1)],
    'POST /api/applications/app-1/portal-submitted': SENT,
    'PATCH /api/applications/app-1': {},
    'POST /api/applications/app-1/answers': {},
    ...extra,
  })
  const onSubmitted = vi.fn()
  render(<AgentFrame applicationId="app-1" onSubmitted={onSubmitted} />)
  return { mocked, onSubmitted }
}

const callsTo = (mocked: ReturnType<typeof routeApi>, path: string) => mocked.mock.calls.filter((c) => c[0] === path)

describe('AgentFrame', () => {
  it('osadza makietę portalu w ramce z oznaczeniem AI/SYMULACJA', async () => {
    setup()
    const frame = await screen.findByTitle('eZUS — 800+')
    expect(frame).toHaveAttribute('src', '/sim/ezus/ezus_800plus')
    expect(frame).toHaveAttribute('sandbox', expect.stringContaining('allow-scripts'))
    expect(screen.getByText('AI · SYMULACJA')).toBeInTheDocument()
  })

  it('nie rusza makiety, dopóki ta nie zgłosi gotowości', async () => {
    setup()
    await screen.findByTitle('eZUS — 800+')
    expect(fills()).toEqual([])
    emit({ type: 'ready' })
    await waitFor(() => expect(fills()).toHaveLength(3))
  })

  it('wykonuje plan w kolejności ze schematu i zatrzymuje się przed wysyłką', async () => {
    const { mocked } = setup()
    await screen.findByTitle('eZUS — 800+')
    emit({ type: 'ready' })

    await screen.findByRole('button', { name: /zatwierdzam i wysyłam/i })
    expect(fills()).toEqual(['applicant_first_name', 'street', 'consent'])
    expect(bridge.posted.find((m) => m.type === 'fill' && m.fieldId === 'consent')).toMatchObject({ value: true }) // bool zostaje bool
    expect(screen.getByText(/gotowe\. sprawdź formularz/i)).toBeInTheDocument()
    // bez zatwierdzenia nic nie jest wysyłane
    expect(bridge.posted.some((m) => m.type === 'submit')).toBe(false)
    expect(callsTo(mocked, '/api/applications/app-1/portal-submitted')).toHaveLength(0)
  })

  it('pokazuje kursor agenta tam, gdzie makieta potwierdziła pole', async () => {
    reduceMotion()
    bridge.autoAck = false // sami potwierdzamy, żeby zatrzymać agenta w trakcie
    setup()
    await screen.findByTitle('eZUS — 800+')
    emit({ type: 'ready' })
    await waitFor(() => expect(fills()).toHaveLength(1))
    emit({ type: 'ack', fieldId: 'applicant_first_name', ok: true, rect: { x: 40, y: 60, width: 100, height: 20 } })
    const cursor = await screen.findByTestId('agent-cursor')
    expect(cursor).toHaveStyle({ transform: 'translate(90px, 70px)' }) // środek pola
    expect(cursor).toHaveAttribute('aria-hidden', 'true')
  })

  it('zatrzymuje się na brakujących danych i pyta rodzica, a po odpowiedzi pobiera nowy plan', async () => {
    const { mocked } = setup([BLOCKED_PLAN, { ...PLAN, steps: [...BLOCKED_PLAN.steps, { field_id: 'child_pesel', label: 'PESEL dziecka', value: '02070803628', reason: 'Podany przez ciebie.' }] }])
    await screen.findByTitle('eZUS — 800+')
    emit({ type: 'ready' })

    expect(await screen.findByRole('heading', { name: /brakuje jeszcze danych/i })).toBeInTheDocument()
    expect(screen.getByLabelText('PESEL dziecka')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /zatwierdzam i wysyłam/i })).not.toBeInTheDocument()
    expect(fills()).toEqual(['applicant_first_name', 'street']) // nie zgadujemy brakującego pola

    await userEvent.type(screen.getByLabelText('PESEL dziecka'), '02070803628')
    await userEvent.click(screen.getByRole('button', { name: /dalej/i }))

    await waitFor(() =>
      expect(mocked).toHaveBeenCalledWith('/api/applications/app-1/answers', { method: 'POST', body: { answers: { child_pesel: '02070803628' } } }),
    )
    await screen.findByRole('button', { name: /zatwierdzam i wysyłam/i })
    expect(callsTo(mocked, '/api/applications/app-1/agent-plan')).toHaveLength(2)
    expect(fills()).toContain('child_pesel')
  })

  it('wysyła dopiero po „Zatwierdzam i wysyłam”, a po potwierdzeniu makiety woła portal-submitted', async () => {
    const { mocked, onSubmitted } = setup()
    await screen.findByTitle('eZUS — 800+')
    emit({ type: 'ready' })
    await userEvent.click(await screen.findByRole('button', { name: /zatwierdzam i wysyłam/i }))

    expect(bridge.posted.at(-1)).toEqual({ type: 'submit' })
    expect(screen.getByRole('button', { name: /zatwierdzam i wysyłam/i })).toBeDisabled() // brak podwójnego kliknięcia
    expect(callsTo(mocked, '/api/applications/app-1/portal-submitted')).toHaveLength(0) // czekamy na makietę

    emit({ type: 'submitted' })
    await waitFor(() => expect(onSubmitted).toHaveBeenCalledWith(SENT))
    expect(callsTo(mocked, '/api/applications/app-1/portal-submitted')).toHaveLength(1)
    expect(mocked).toHaveBeenCalledWith('/api/applications/app-1/portal-submitted', { method: 'POST' })
    expect(screen.getByText(/wniosek złożony w makiecie portalu/i)).toBeInTheDocument()
  })

  it('ignoruje `submitted`, zanim rodzic zatwierdzi (agent jeszcze pracuje)', async () => {
    const { mocked, onSubmitted } = setup()
    await screen.findByTitle('eZUS — 800+')
    bridge.autoAck = false
    emit({ type: 'ready' })
    await waitFor(() => expect(fills()).toHaveLength(1))
    emit({ type: 'submitted' })
    await new Promise((r) => setTimeout(r, 20))
    expect(callsTo(mocked, '/api/applications/app-1/portal-submitted')).toHaveLength(0)
    expect(onSubmitted).not.toHaveBeenCalled()
  })

  it('gdy makieta odmówi wysyłki (brak pól), wraca do podglądu z komunikatem', async () => {
    setup()
    await screen.findByTitle('eZUS — 800+')
    emit({ type: 'ready' })
    await userEvent.click(await screen.findByRole('button', { name: /zatwierdzam i wysyłam/i }))
    emit({ type: 'invalid', fieldIds: ['street'] })
    expect(await screen.findByRole('alert')).toHaveTextContent(/uzupełnij zaznaczone pola/i)
    expect(screen.getByRole('button', { name: /zatwierdzam i wysyłam/i })).toBeEnabled()
  })

  it('zapisuje we wniosku pole, które rodzic zmienił ręcznie w makiecie', async () => {
    const { mocked } = setup()
    await screen.findByTitle('eZUS — 800+')
    emit({ type: 'ready' })
    await screen.findByRole('button', { name: /zatwierdzam i wysyłam/i })
    emit({ type: 'edited', fieldId: 'street', value: 'Szewska' })
    await waitFor(() =>
      expect(mocked).toHaveBeenCalledWith('/api/applications/app-1', { method: 'PATCH', body: { values: { street: 'Szewska' } } }),
    )
  })

  it('informuje o polach odrzuconych przez makietę', async () => {
    bridge.refuse.add('street')
    setup()
    await screen.findByTitle('eZUS — 800+')
    emit({ type: 'ready' })
    expect(await screen.findByRole('note')).toHaveTextContent(/nie przyjęła pól: Ulica/i)
  })

  it('błąd planu (np. model niedostępny) pokazuje komunikat z API', async () => {
    routeApi({ 'POST /api/applications/app-1/agent-plan': new ApiError(503, 'Asystent AI jest chwilowo niedostępny.') })
    render(<AgentFrame applicationId="app-1" onSubmitted={vi.fn()} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Asystent AI jest chwilowo niedostępny.')
    expect(screen.queryByTitle('eZUS — 800+')).not.toBeInTheDocument()
  })
})
