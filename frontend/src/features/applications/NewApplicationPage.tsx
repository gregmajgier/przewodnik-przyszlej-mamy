import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import { describeChild } from '../../lib/format'
import { useSession } from '../../lib/session'
import { CHANNEL_LABEL } from './types'
import type { Application, Channel, FormEntry, FormsResponse } from './types'
import './applications.css'

const API_URL: string = import.meta.env.VITE_API_URL ?? ''

export default function NewApplicationPage() {
  const { family, loading } = useSession()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const requested = params.get('form') ?? ''
  const [data, setData] = useState<FormsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [code, setCode] = useState(requested)
  const [childId, setChildId] = useState('')
  const [channel, setChannel] = useState<Channel | ''>('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!family) return
    let cancelled = false
    api<FormsResponse>('/api/applications/forms')
      .then((f) => !cancelled && setData(f))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.detail : 'Nie udało się wczytać listy wniosków.'))
    return () => {
      cancelled = true
    }
  }, [family])

  if (loading) return <p role="status">Ładowanie…</p>
  if (!family) return <Navigate to="/start" replace />

  const forms = data?.forms ?? []
  const form: FormEntry | undefined = forms.find((f) => f.code === code)
  const recommended = new Set(data?.recommended_flow ?? [])
  // wnioski nie dotyczą dzieci w sytuacji straty — poza wsparciem po stracie (`loss_ok`)
  const children = family.children.filter((c) => c.situation !== 'loss' || form?.loss_ok === true)
  const unsupported = data !== null && requested !== '' && !forms.some((f) => f.code === requested)
  const needsChild = form?.requires_child === true
  const effectiveChild = childId || (needsChild && children.length === 1 ? children[0].id : '')
  const effectiveChannel = channel || form?.default_channel || ''
  const canStart = form !== undefined && (!needsChild || effectiveChild !== '') && !busy

  async function start(e: FormEvent) {
    e.preventDefault()
    if (!form || !canStart) return
    setBusy(true)
    setError(null)
    try {
      const body: Record<string, string> = { form_code: form.code }
      if (effectiveChild) body.child_id = effectiveChild
      if (form.channels.length > 1 && effectiveChannel) body.channel = effectiveChannel
      const app = await api<Application>('/api/applications', { method: 'POST', body })
      navigate(`/wnioski/${app.id}`, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Nie udało się założyć wniosku.')
      setBusy(false)
    }
  }

  return (
    <div className="stack" style={{ maxWidth: '40rem' }}>
      <h1>Nowy wniosek</h1>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {unsupported && (
        <p role="note" className="notice">
          Dla wniosku <strong>{requested}</strong> nie ma jeszcze kreatora w aplikacji. Wybierz inny wniosek albo pobierz{' '}
          <a href={`${API_URL}/api/wnioski/${encodeURIComponent(requested)}/pdf`}>pusty formularz</a>.
        </p>
      )}
      {!data && !error && <p role="status">Wczytuję listę wniosków…</p>}

      {data && (
        <form className="card stack" onSubmit={start} noValidate>
          <div className="field">
            <label htmlFor="form-code">Rodzaj wniosku</label>
            <select
              id="form-code"
              value={code}
              onChange={(e) => {
                setCode(e.target.value)
                setChannel('')
              }}
            >
              <option value="">— wybierz —</option>
              {forms.map((f) => (
                <option key={f.code} value={f.code}>
                  {f.name}
                  {recommended.has(f.code) ? ' (polecany)' : ''}
                </option>
              ))}
            </select>
          </div>

          {form?.deadline && <p className="muted">Termin: {form.deadline}</p>}

          {needsChild && (
            <div className="field">
              <label htmlFor="child">Dziecko, którego dotyczy wniosek</label>
              {children.length === 0 ? (
                <p className="muted">
                  Najpierw dodaj dziecko w zakładce <Link to="/rodzina">Rodzina</Link>.
                </p>
              ) : (
                <select id="child" value={effectiveChild} onChange={(e) => setChildId(e.target.value)}>
                  <option value="">— wybierz —</option>
                  {children.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({describeChild(c)})
                    </option>
                  ))}
                </select>
              )}
            </div>
          )}

          {form && form.channels.length > 1 && (
            <fieldset className="stack channel-picker">
              <legend>Jak złożyć wniosek?</legend>
              {form.channels.map((c) => (
                <label key={c} className="row">
                  <input type="radio" name="channel" checked={effectiveChannel === c} onChange={() => setChannel(c)} />
                  <span>{CHANNEL_LABEL[c]}</span>
                </label>
              ))}
            </fieldset>
          )}
          {form?.only_electronic && <p className="muted">Ten wniosek składa się wyłącznie elektronicznie — wypełni go dla Ciebie agent.</p>}

          <div className="row">
            <button type="submit" className="btn" disabled={!canStart}>
              Zacznij wypełnianie
            </button>
            <Link to="/wnioski">Anuluj</Link>
          </div>
        </form>
      )}
    </div>
  )
}
