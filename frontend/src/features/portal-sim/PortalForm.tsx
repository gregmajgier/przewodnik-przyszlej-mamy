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
const KIND_NAME: Record<PortalKind, string> = { pue: 'PUE ZUS', empatia: 'Emp@tia' }

/** Numer UPO (Urzędowe Poświadczenie Przedłożenia) — wyłącznie testowy, losowany po stronie makiety. */
function makeUpoNumber(): string {
  const n = Math.floor(Math.random() * 1e8)
    .toString()
    .padStart(8, '0')
  return `UPO/${new Date().getFullYear()}/${n}`
}

const PUE_MENU = ['Pulpit', 'Dokumenty i wiadomości', 'Moje dane', 'Ubezpieczony']

export default function PortalForm({ portalId, kind }: { portalId: string; kind: PortalKind }) {
  const [schema, setSchema] = useState<PortalSchema | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [values, setValues] = useState<Record<string, FieldValue>>({})
  const [filled, setFilled] = useState<Set<string>>(new Set())
  const [invalid, setInvalid] = useState<Set<string>>(new Set())
  const [submitted, setSubmitted] = useState<{ upo: string; at: Date } | null>(null)
  // pole świeżo wypełnione przez agenta — po renderze odsyłamy potwierdzenie z położeniem pola (dla kursora)
  const [ackRequest, setAckRequest] = useState<{ fieldId: string; n: number } | null>(null)
  const counter = useRef(0)
  const valuesRef = useRef(values)

  useEffect(() => {
    let cancelled = false
    api<PortalSchema>(`/api/applications/portals/${encodeURIComponent(portalId)}`)
      .then((s) => {
        if (cancelled) return
        setSchema(s)
        const initial = initialValues(s)
        valuesRef.current = initial
        setValues(initial)
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
      const v = valuesRef.current[f.id]
      return f.type === 'bool' ? v !== true : typeof v !== 'string' || v.trim() === ''
    })
    setInvalid(new Set(missing.map((f) => f.id)))
    if (missing.length > 0) {
      postToParent({ type: 'invalid', fieldIds: missing.map((f) => f.id) })
      return
    }
    setSubmitted({ upo: makeUpoNumber(), at: new Date() })
    postToParent({ type: 'submitted' })
  }, [schema])

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
      valuesRef.current = { ...valuesRef.current, [field.id]: value }
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
    valuesRef.current = { ...valuesRef.current, [field.id]: value }
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
  const isPue = kind === 'pue'
  return (
    <div className={`sim sim-page sim-${kind}`} data-portal={portalId}>
      {isPue ? (
        <>
          <div className="sim-topbar">
            <span className="sim-brand">PUE ZUS</span>
            <span className="sim-topbar-sub">Platforma Usług Elektronicznych</span>
            <span className="sim-testtag">DANE TESTOWE</span>
          </div>
          <div className="sim-session" role="note">
            Zalogowano przez Profil Zaufany · konto testowe
          </div>
          <nav className="sim-menu" aria-label="Menu PUE ZUS (makieta)">
            {PUE_MENU.map((m) => (
              <span key={m} className={m === 'Dokumenty i wiadomości' ? 'is-active' : undefined}>
                {m}
              </span>
            ))}
          </nav>
          <p className="sim-crumbs">Dokumenty i wiadomości › Utwórz dokument › Wniosek</p>
          <header className="sim-header">
            <h1>{schema.title.replace(/^PUE ZUS — /, '')}</h1>
          </header>
        </>
      ) : (
        <header className="sim-header">
          <span className="sim-brand">{name}</span>
          <h1>{schema.title}</h1>
        </header>
      )}

      {submitted ? (
        <section className="sim-done" role="status" aria-live="polite">
          <h2>Wniosek złożony</h2>
          {isPue ? (
            <>
              <ol className="sim-steps">
                <li>Dokument podpisany Profilem Zaufanym</li>
                <li>Dokument wysłany do ZUS</li>
                <li>Wystawiono Urzędowe Poświadczenie Przedłożenia (UPO)</li>
              </ol>
              <dl className="sim-upo">
                <dt>Numer UPO</dt>
                <dd>{submitted.upo}</dd>
                <dt>Data i godzina przedłożenia</dt>
                <dd>{submitted.at.toLocaleString('pl-PL')}</dd>
                <dt>Status</dt>
                <dd>Przyjęty, oczekuje na rozpatrzenie</dd>
              </dl>
              <p>Odpowiedź ZUS pojawi się w „Dokumenty i wiadomości”, a mRodzina pokaże ją przy wniosku.</p>
            </>
          ) : (
            <p>Potwierdzenie i decyzja trafią na Twoją skrzynkę, a mRodzina pokaże je przy wniosku.</p>
          )}
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
                        type={f.type === 'date' ? 'date' : /kwot|dochód|zł|wynagrodz|podstaw|zadłuż/i.test(f.label) ? 'number' : 'text'}
                        min={/kwot|dochód|zł|wynagrodz|podstaw|zadłuż/i.test(f.label) ? 0 : undefined}
                        step="0.01"
                        inputMode={/kwot|dochód|zł|wynagrodz|podstaw|zadłuż/i.test(f.label) ? 'decimal' : undefined}
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
            {isPue ? 'Podpisz i wyślij' : 'Wyślij wniosek'}
          </button>
        </form>
      )}
    </div>
  )
}
