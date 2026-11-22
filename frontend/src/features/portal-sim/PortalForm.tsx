import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../../lib/api'
import type { PortalKind } from '../applications/types'
import { listenToParent, postToParent } from './agentBridge'
import type { FieldValue, ToFrame } from './agentBridge'
import { coerceFill, initialValues } from './portalSchema'
import type { PortalField, PortalSchema } from './portalSchema'
import './portal-sim.css'
import { openNativePicker } from '../../ui/nativePicker'

const domId = (fieldId: string) => `sim-field-${fieldId}`
const KIND_NAME: Record<PortalKind, string> = { ezus: 'eZUS', empatia: 'Emp@tia' }

export default function PortalForm({ portalId, kind }: { portalId: string; kind: PortalKind }) {
  const [schema, setSchema] = useState<PortalSchema | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [values, setValues] = useState<Record<string, FieldValue>>({})
  const [filled, setFilled] = useState<Set<string>>(new Set())
  const [invalid, setInvalid] = useState<Set<string>>(new Set())
  const [submitted, setSubmitted] = useState(false)
  // pole świeżo wypełnione przez agenta — po renderze odsyłamy potwierdzenie z położeniem pola (dla kursora)
  const [ackRequest, setAckRequest] = useState<{ fieldId: string; n: number } | null>(null)
  const counter = useRef(0)

  useEffect(() => {
    let cancelled = false
    api<PortalSchema>(`/api/applications/portals/${encodeURIComponent(portalId)}`)
      .then((s) => {
        if (cancelled) return
        setSchema(s)
        setValues(initialValues(s))
      })
      .catch((e) => {
        if (cancelled) return
        setError(
          e instanceof ApiError && e.status === 401
            ? 'Zaloguj się w mRodzinie, żeby zobaczyć formularz.'
            : e instanceof ApiError
              ? e.detail
              : 'Nie udało się wczytać formularza.',
        )
      })
    return () => {
      cancelled = true
    }
  }, [portalId])

  const trySubmit = useCallback(() => {
    if (!schema) return
    const missing = schema.fields.filter((f) => {
      if (!f.required) return false
      const v = values[f.id]
      return f.type === 'bool' ? v !== true : typeof v !== 'string' || v.trim() === ''
    })
    setInvalid(new Set(missing.map((f) => f.id)))
    if (missing.length > 0) {
      postToParent({ type: 'invalid', fieldIds: missing.map((f) => f.id) })
      return
    }
    setSubmitted(true)
    postToParent({ type: 'submitted' })
  }, [schema, values])

  const handleParent = useCallback(
    (msg: ToFrame) => {
      if (!schema) return
      if (msg.type === 'submit') {
        trySubmit()
        return
      }
      // plan agenta: tylko pola ze schematu makiety i wartości zgodne z typem (reszta jest odrzucana)
      const field = schema.fields.find((f) => f.id === msg.fieldId)
      const value = field ? coerceFill(field, msg.value) : null
      if (!field || value === null) {
        postToParent({ type: 'ack', fieldId: msg.fieldId, ok: false })
        return
      }
      setValues((prev) => ({ ...prev, [field.id]: value }))
      setFilled((prev) => new Set(prev).add(field.id))
      setAckRequest({ fieldId: field.id, n: ++counter.current })
    },
    [schema, trySubmit],
  )

  // po załadowaniu schematu zgłaszamy gotowość; od tej chwili obsługujemy polecenia agenta
  useEffect(() => {
    if (!schema) return
    const off = listenToParent(handleParent)
    postToParent({ type: 'ready' })
    return off
  }, [schema, handleParent])

  useEffect(() => {
    if (!ackRequest) return
    const el = document.getElementById(domId(ackRequest.fieldId))
    el?.scrollIntoView?.({ block: 'center' })
    const r = el?.getBoundingClientRect()
    postToParent({
      type: 'ack',
      fieldId: ackRequest.fieldId,
      ok: true,
      rect: r ? { x: r.x, y: r.y, width: r.width, height: r.height } : undefined,
    })
  }, [ackRequest])

  function edit(field: PortalField, value: FieldValue) {
    setValues((prev) => ({ ...prev, [field.id]: value }))
    setInvalid((prev) => {
      const next = new Set(prev)
      next.delete(field.id)
      return next
    })
    postToParent({ type: 'edited', fieldId: field.id, value })
  }

  if (error) {
    return (
      <div className="sim sim-page">
        <p role="alert" className="alert">
          {error}
        </p>
      </div>
    )
  }
  if (!schema) {
    return (
      <p role="status" className="sim sim-page">
        Ładowanie formularza…
      </p>
    )
  }

  const name = KIND_NAME[kind]
  return (
    <div className={`sim sim-page sim-${kind}`} data-portal={portalId}>
      <header className="sim-header">
        <span className="sim-brand">{name}</span>
        <h1>{schema.title}</h1>
      </header>

      {submitted ? (
        <section className="sim-done" role="status" aria-live="polite">
          <h2>Wniosek złożony</h2>
          <p>Potwierdzenie i decyzja trafią na Twoją skrzynkę, a mRodzina pokaże je przy wniosku.</p>
        </section>
      ) : (
        <form
          className="sim-form"
          onSubmit={(e) => {
            e.preventDefault()
            trySubmit()
          }}
          noValidate
        >
          {schema.fields.map((f) => {
            const id = domId(f.id)
            const bad = invalid.has(f.id)
            const cls = `field sim-field${filled.has(f.id) ? ' is-agent-filled' : ''}${bad ? ' is-invalid' : ''}`
            const common = { id, name: f.id, 'aria-invalid': bad || undefined, 'aria-required': f.required || undefined }
            return (
              <div key={f.id} className={cls}>
                {f.type === 'bool' ? (
                  <label className="sim-check">
                    <input
                      {...common}
                      type="checkbox"
                      checked={values[f.id] === true}
                      onChange={(e) => edit(f, e.target.checked)}
                    />
                    <span>{f.label}</span>
                  </label>
                ) : (
                  <>
                    <label htmlFor={id}>
                      {f.label}
                      {f.required && <span aria-hidden="true"> *</span>}
                    </label>
                    {f.type === 'choice' ? (
                      <select {...common} value={String(values[f.id] ?? '')} onChange={(e) => edit(f, e.target.value)}>
                        <option value="">Wybierz</option>
                        {(f.choices ?? []).map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        {...common}
                        type={f.type === 'date' ? 'date' : 'text'}
                        onClick={f.type === 'date' ? (e) => openNativePicker(e.currentTarget) : undefined}
                        value={String(values[f.id] ?? '')}
                        autoComplete="off"
                        onChange={(e) => edit(f, e.target.value)}
                      />
                    )}
                  </>
                )}
                {bad && <span className="sim-error">To pole jest wymagane.</span>}
              </div>
            )
          })}
          <button type="submit" className="btn sim-submit">
            Wyślij wniosek
          </button>
        </form>
      )}
    </div>
  )
}
