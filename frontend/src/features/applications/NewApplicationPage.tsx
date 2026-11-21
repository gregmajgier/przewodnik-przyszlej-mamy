import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import { useSession } from '../../lib/session'
import { Button } from '../../ui/Button'
import { Icon } from '../../ui/Icon'
import { Avatar, PageHeader, Pill } from '../../ui/controls'
import { childLabel, childTone, describeAge } from '../matters/model'
import { CHANNEL_LABEL } from './types'
import type { Application, Channel, FormEntry, FormsResponse } from './types'
import '../../ui/ui.css'
import '../onboarding/flow.css'
import './applications.css'

const API_URL: string = import.meta.env.VITE_API_URL ?? ''

export default function NewApplicationPage() {
  const { family } = useSession()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const requested = params.get('form') ?? ''
  const [data, setData] = useState<FormsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [code, setCode] = useState(requested)
  const [childId, setChildId] = useState('')
  const [channel, setChannel] = useState<Channel | ''>('')
  const [busy, setBusy] = useState(false)
  const [showAll, setShowAll] = useState(false)
  // po wyborze lista zwija się do jednej karty, żeby dalsze kroki były od razu pod nią
  const [picking, setPicking] = useState(false)

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

  const forms = useMemo(() => data?.forms ?? [], [data])
  const recommended = useMemo(() => new Set(data?.recommended_flow ?? []), [data])
  if (!family) return null

  const form: FormEntry | undefined = forms.find((f) => f.code === code)
  // wnioski nie dotyczą dzieci w sytuacji straty — poza wsparciem po stracie (`loss_ok`)
  const children = family.children.filter((c) => c.situation !== 'loss' || form?.loss_ok === true)
  const unsupported = data !== null && requested !== '' && !forms.some((f) => f.code === requested)
  const needsChild = form?.requires_child === true
  const effectiveChild = childId || (needsChild && children.length === 1 ? children[0].id : '')
  const effectiveChannel = channel || form?.default_channel || ''
  const canStart = form !== undefined && !picking && (!needsChild || effectiveChild !== '') && !busy
  const ordered = [...forms].sort((a, b) => Number(recommended.has(b.code)) - Number(recommended.has(a.code)))
  const collapsed = form !== undefined && !picking
  const top = ordered.slice(0, 6)
  const visible = collapsed ? [form] : showAll || (form && !top.includes(form)) ? ordered : top

  function choose(f: FormEntry) {
    if (f.code !== code) {
      setCode(f.code)
      setChannel('')
    }
    setPicking(false)
  }

  async function start() {
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
    <div className="page page-narrow">
      <PageHeader title="Nowy wniosek" eyebrow="Wypełnimy go za Ciebie" back="/wnioski">
        <p className="muted">Wybierz, co chcesz złożyć — dane uzupełnimy z ZUS, mObywatela i Waszego profilu.</p>
      </PageHeader>

      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {unsupported && (
        <p role="note" className="notice">
          Dla wniosku <strong>{requested}</strong> nie mamy jeszcze kreatora. Wybierz inny wniosek albo pobierz{' '}
          <a href={`${API_URL}/api/wnioski/${encodeURIComponent(requested)}/pdf`}>pusty formularz</a>.
        </p>
      )}
      {!data && !error && <div className="skeleton" style={{ height: '16rem' }} role="status" aria-label="Wczytuję listę wniosków" />}

      {data && (
        <div className="stack">
          <section aria-labelledby="pick-h">
            <div className="section-head" style={{ marginBottom: '0.75rem' }}>
              <h2 id="pick-h">Rodzaj wniosku</h2>
              {collapsed && (
                <button type="button" className="link-button" onClick={() => setPicking(true)}>
                  Zmień wniosek
                </button>
              )}
            </div>
            <div className="form-picker" role="radiogroup" aria-labelledby="pick-h">
              {visible.map((f) => (
                <button
                  key={f.code}
                  type="button"
                  role="radio"
                  aria-checked={code === f.code}
                  className="form-option"
                  onClick={() => (collapsed ? setPicking(true) : choose(f))}
                >
                  <span className="icon-tile tone-sky">
                    <Icon name={f.channels.includes('portal_agent') ? 'globe' : 'doc'} size={20} />
                  </span>
                  <span className="form-option-main">
                    <strong>{f.name}</strong>
                    <span>{[f.institution, f.deadline ? `termin: ${f.deadline}` : null].filter(Boolean).join(' · ')}</span>
                  </span>
                  {recommended.has(f.code) && <Pill tone="pink">Polecany</Pill>}
                </button>
              ))}
            </div>
            {!collapsed && visible.length < ordered.length && (
              <button type="button" className="flow-skip" style={{ marginTop: '0.5rem' }} onClick={() => setShowAll(true)}>
                Pokaż wszystkie ({ordered.length})
              </button>
            )}
          </section>

          {collapsed && needsChild && (
            <section aria-labelledby="child-h">
              <h2 id="child-h">Którego dziecka dotyczy?</h2>
              {children.length === 0 ? (
                <p className="muted">
                  Najpierw dodaj dziecko w zakładce <Link to="/rodzina">Rodzina</Link>.
                </p>
              ) : (
                <div className="form-picker" role="radiogroup" aria-labelledby="child-h">
                  {children.map((c, i) => (
                    <button
                      key={c.id}
                      type="button"
                      role="radio"
                      aria-checked={effectiveChild === c.id}
                      className="form-option"
                      onClick={() => setChildId(c.id)}
                    >
                      <Avatar name={childLabel(c)} tone={childTone(i)} icon={c.status === 'expected' ? 'baby' : undefined} size={40} />
                      <span className="form-option-main">
                        <strong>{childLabel(c)}</strong>
                        <span>{describeAge(c)}</span>
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </section>
          )}

          {collapsed && form.channels.length > 1 && (
            <div className="channel-picker" role="radiogroup" aria-label="Jak złożyć wniosek?">
              <h2 style={{ margin: 0 }}>Jak złożyć wniosek?</h2>
              {form.channels.map((c) => (
                <button
                  key={c}
                  type="button"
                  role="radio"
                  aria-checked={effectiveChannel === c}
                  className="channel-option"
                  onClick={() => setChannel(c)}
                >
                  <Icon name={c === 'portal_agent' ? 'globe' : c === 'employer_email' ? 'mail' : 'download'} size={20} />
                  <span>{CHANNEL_LABEL[c]}</span>
                  <span className="channel-radio" aria-hidden="true" />
                </button>
              ))}
            </div>
          )}
          {collapsed && form.only_electronic && (
            <p className="notice">
              <Icon name="sparkle" size={18} style={{ display: 'inline', verticalAlign: '-3px' }} /> Ten wniosek składa się
              tylko elektronicznie — formularz online wypełni za Ciebie agent.
            </p>
          )}

          <Button block icon="arrowRight" disabled={!canStart} onClick={() => void start()}>
            {busy ? 'Przygotowuję…' : 'Zacznij wypełnianie'}
          </Button>
        </div>
      )}
    </div>
  )
}
