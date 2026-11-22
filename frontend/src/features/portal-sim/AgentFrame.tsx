import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../../lib/api'
import { prefersReducedMotion } from '../../lib/motion'
import MissingFieldsStep from '../applications/MissingFieldsStep'
import { Button } from '../../ui/Button'
import { Icon } from '../../ui/Icon'
import { Progress } from '../../ui/controls'
import type { AgentPlan, AgentStep, AnswerValue, Application } from '../applications/types'
import AgentCursor from './AgentCursor'
import { listenFromFrame, postToFrame } from './agentBridge'
import type { FieldValue, Rect } from './agentBridge'
import './portal-sim.css'

/** Pauza między krokami agenta (ms) — żeby rodzic widział, co się dzieje. Przy reduced-motion: 0. */
export const STEP_DELAY_MS = 450
/** Ile czekamy na potwierdzenie pola z makiety, zanim pójdziemy dalej. */
export const ACK_TIMEOUT_MS = 3000

type Phase = 'loading' | 'running' | 'blocked' | 'review' | 'submitting' | 'done' | 'error'
type Ack = { ok: boolean; rect?: Rect }

interface Props {
  applicationId: string
  /** Wołane po zatwierdzeniu wysyłki w makiecie i potwierdzeniu przez API (`portal-submitted`). */
  onSubmitted: (app: Application) => void
}

const sleep = (ms: number) => new Promise<void>((resolve) => window.setTimeout(resolve, ms))
const toFieldValue = (v: unknown): FieldValue => (typeof v === 'boolean' ? v : String(v ?? ''))
const errorText = (e: unknown, fallback: string) => (e instanceof ApiError ? e.detail : fallback)

/**
 * Agent „klikający” w makiecie portalu:
 * pobiera plan (`/agent-plan`), wykonuje kroki po kolei z widocznym kursorem, zatrzymuje się na brakujących danych
 * (pyta rodzica) oraz przed wysyłką — wysyła dopiero po „Zatwierdzam i wysyłam”. Rodzic może sam edytować
 * dowolne pole w makiecie; zmiany zapisujemy we wniosku.
 */
export default function AgentFrame({ applicationId, onSubmitted }: Props) {
  const frameRef = useRef<HTMLIFrameElement>(null)
  const [plan, setPlan] = useState<AgentPlan | null>(null)
  const [ready, setReady] = useState(false)
  const [runKey, setRunKey] = useState(0)
  const [phase, setPhase] = useState<Phase>('loading')
  const [progress, setProgress] = useState(0)
  const [cursor, setCursor] = useState<{ x: number; y: number } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [rejected, setRejected] = useState<string[]>([])
  const [answering, setAnswering] = useState(false)
  const acks = useRef(new Map<string, (ack: Ack) => void>())
  const phaseRef = useRef<Phase>('loading')
  const onSubmittedRef = useRef(onSubmitted)

  useEffect(() => {
    phaseRef.current = phase
    onSubmittedRef.current = onSubmitted
  })

  // 1. plan agenta (ponownie po odpowiedziach na brakujące dane)
  useEffect(() => {
    let cancelled = false
    api<AgentPlan>(`/api/applications/${applicationId}/agent-plan`, { method: 'POST' })
      .then((p) => {
        if (cancelled) return
        setError(null)
        setPlan(p)
      })
      .catch((e) => {
        if (cancelled) return
        setError(errorText(e, 'Nie udało się przygotować planu agenta.'))
        setPhase('error')
      })
    return () => {
      cancelled = true
    }
  }, [applicationId, runKey])

  // 2. wiadomości z makiety (tylko ten sam origin i tylko z naszej ramki — patrz agentBridge)
  useEffect(() => {
    return listenFromFrame(
      (msg) => {
        switch (msg.type) {
          case 'ready':
            setReady(true)
            break
          case 'ack':
            acks.current.get(msg.fieldId)?.({ ok: msg.ok, rect: msg.rect })
            break
          case 'edited':
            // rodzic przejął pole: zapisujemy zmianę we wniosku, żeby PDF/dane były spójne z makietą
            api(`/api/applications/${applicationId}`, { method: 'PATCH', body: { values: { [msg.fieldId]: msg.value } } }).catch((e) =>
              setError(errorText(e, 'Nie udało się zapisać zmiany pola.')),
            )
            break
          case 'invalid':
            if (phaseRef.current === 'submitting') {
              setPhase('review')
              setError('Makieta nie przyjęła wniosku. Uzupełnij zaznaczone pola i zatwierdź ponownie.')
            }
            break
          case 'submitted':
            if (phaseRef.current === 'review' || phaseRef.current === 'submitting') {
              setPhase('submitting')
              api<Application>(`/api/applications/${applicationId}/portal-submitted`, { method: 'POST' })
                .then((app) => {
                  setPhase('done')
                  onSubmittedRef.current(app)
                })
                .catch((e) => {
                  setPhase('review')
                  setError(errorText(e, 'Nie udało się zapisać złożenia wniosku.'))
                })
            }
            break
        }
      },
      () => frameRef.current?.contentWindow,
    )
  }, [applicationId])

  // 3. wykonanie planu krok po kroku
  useEffect(() => {
    if (!plan || !ready) return
    let cancelled = false

    function fill(step: AgentStep): Promise<Ack | null> {
      return new Promise((resolve) => {
        const timer = window.setTimeout(() => {
          acks.current.delete(step.field_id)
          resolve(null) // makieta nie odpowiedziała — idziemy dalej
        }, ACK_TIMEOUT_MS)
        acks.current.set(step.field_id, (ack) => {
          window.clearTimeout(timer)
          acks.current.delete(step.field_id)
          resolve(ack)
        })
        postToFrame(frameRef.current?.contentWindow, { type: 'fill', fieldId: step.field_id, value: toFieldValue(step.value) })
      })
    }

    async function run(current: AgentPlan) {
      const reduced = prefersReducedMotion()
      const refused: string[] = []
      setPhase('running')
      setProgress(0)
      setRejected([])
      for (const [i, step] of current.steps.entries()) {
        const ack = await fill(step)
        if (cancelled) return
        if (ack && !ack.ok) refused.push(step.label)
        if (ack?.rect) setCursor({ x: ack.rect.x + ack.rect.width / 2, y: ack.rect.y + ack.rect.height / 2 })
        setProgress(i + 1)
        await sleep(reduced ? 0 : STEP_DELAY_MS)
        if (cancelled) return
      }
      setRejected(refused)
      // zatrzymujemy się: albo brakuje danych (pytamy), albo czekamy na zatwierdzenie rodzica
      setPhase(current.blocked.length > 0 ? 'blocked' : 'review')
    }

    void run(plan)
    return () => {
      cancelled = true
    }
  }, [plan, ready])

  const answer = useCallback(
    async (fieldId: string, value: AnswerValue) => {
      setAnswering(true)
      setError(null)
      try {
        await api(`/api/applications/${applicationId}/answers`, { method: 'POST', body: { answers: { [fieldId]: value } } })
        setPhase('loading')
        setRunKey((k) => k + 1) // nowy plan uwzględni odpowiedź; agent wypełni całość jeszcze raz
      } catch (e) {
        setError(errorText(e, 'Nie udało się zapisać odpowiedzi.'))
      } finally {
        setAnswering(false)
      }
    },
    [applicationId],
  )

  function approve() {
    setError(null)
    setPhase('submitting')
    postToFrame(frameRef.current?.contentWindow, { type: 'submit' })
  }

  const total = plan?.steps.length ?? 0

  return (
    <section className="agent-panel" aria-labelledby="agent-h">
      <div className="agent-head">
        <span className="agent-avatar" aria-hidden="true">
          <Icon name="sparkle" size={22} />
        </span>
        <div>
          <h2 id="agent-h">Agent wypełnia formularz online</h2>
          <p className="muted small">
            Wpisuje dane z Waszego profilu. Możesz kliknąć dowolne pole i je poprawić. Nic nie zostanie wysłane, dopóki tego
            nie zatwierdzisz.
          </p>
        </div>
      </div>

      {total > 0 && phase === 'running' && <Progress value={progress / total} label="Postęp wypełniania" />}
      <div className="agent-status" role="status" aria-live="polite">
        {phase === 'loading' && 'Przygotowuję plan…'}
        {phase === 'running' && `Wypełniam formularz: krok ${Math.min(progress + 1, total)} z ${total}`}
        {phase === 'blocked' && 'Zatrzymałem się: potrzebuję jeszcze kilku danych.'}
        {phase === 'review' && 'Gotowe. Sprawdź formularz i zatwierdź wysyłkę.'}
        {phase === 'submitting' && 'Wysyłam…'}
        {phase === 'done' && 'Wniosek złożony.'}
      </div>

      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {rejected.length > 0 && (
        <p role="note" className="notice">
          Formularz nie przyjął pól: {rejected.join(', ')}. Uzupełnij je ręcznie.
        </p>
      )}

      {plan && (
        <div className="agent-stage">
          <div className="browser-bar" aria-hidden="true">
            <span className="browser-dots">
              <i />
              <i />
              <i />
            </span>
            <span className="browser-url">
              <Icon name="lock" size={13} /> {plan.kind === 'ezus' ? 'eZUS' : 'Emp@tia'} · {plan.title ?? 'formularz'}
            </span>
          </div>
          <iframe
            ref={frameRef}
            className="agent-frame"
            title={plan.title ?? 'Formularz online'}
            src={`/sim/${plan.kind}/${plan.portal_id}`}
            sandbox="allow-scripts allow-same-origin"
          />
          {cursor && phase === 'running' && <AgentCursor x={cursor.x} y={cursor.y} />}
        </div>
      )}

      {phase === 'blocked' && plan && (
        <MissingFieldsStep questions={plan.blocked} onAnswer={answer} busy={answering} error={null} />
      )}

      {(phase === 'review' || phase === 'submitting') && (
        <Button block disabled={phase === 'submitting'} onClick={approve} icon="arrowRight">
          Zatwierdzam i wysyłam
        </Button>
      )}
    </section>
  )
}
