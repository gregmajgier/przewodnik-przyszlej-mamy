import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import { formatDate, timeAgo } from '../../lib/format'
import { useSession } from '../../lib/session'
import { Button } from '../../ui/Button'
import { Icon } from '../../ui/Icon'
import { PageHeader, Pill } from '../../ui/controls'
import type { MailThread } from './mailTypes'
import { CHANNEL_SHORT, senderLabel, SHORT, STATUS_TONE } from './useApplications'
import MissingFieldsStep from './MissingFieldsStep'
import PreviewStep from './PreviewStep'
import SendStep from './SendStep'
import { isFinal, STATUS_LABEL } from './types'
import type { AnswerValue, Application, Channel, FormEntry, FormsResponse } from './types'
import './applications.css'

type StepKey = 'data' | 'preview' | 'send' | 'done'
const STEPS: { key: StepKey; label: string }[] = [
  { key: 'data', label: 'Dane' },
  { key: 'preview', label: 'Podgląd' },
  { key: 'send', label: 'Złożenie' },
  { key: 'done', label: 'Gotowe' },
]

const errText = (e: unknown, fallback: string) => (e instanceof ApiError ? e.detail : fallback)
const formatDateTime = (iso: string) => new Date(iso).toLocaleString('pl-PL', { dateStyle: 'medium', timeStyle: 'short' })

function Stepper({ current }: { current: StepKey }) {
  const index = STEPS.findIndex((s) => s.key === current)
  return (
    <ol className="stepper" aria-label="Postęp składania wniosku">
      {STEPS.map((s, i) => (
        <li key={s.key} aria-current={s.key === current ? 'step' : undefined} className={i < index ? 'is-past' : ''}>
          <span className="stepper-n">{i < index ? <Icon name="check" size={14} stroke={2.6} /> : i + 1}</span>
          <span className="stepper-label">{s.label}</span>
        </li>
      ))}
    </ol>
  )
}

/** Korespondencja w sprawie wniosku — wczytana z Gmaila; odpowiedzi czyta asystent i aktualizuje status. */
function Correspondence({ appId }: { appId: string }) {
  const [thread, setThread] = useState<MailThread | null | undefined>(undefined)
  useEffect(() => {
    let cancelled = false
    api<MailThread[]>('/api/mail/threads')
      .then((ts) => !cancelled && setThread(ts.find((t) => t.application.id === appId) ?? null))
      .catch(() => !cancelled && setThread(null))
    return () => {
      cancelled = true
    }
  }, [appId])
  if (!thread || thread.messages.length === 0) return null
  return (
    <section className="section" aria-labelledby="mail-h">
      <h2 id="mail-h">Korespondencja</h2>
      <ol className="mail-thread">
        {thread.messages.map((m) => (
          <li key={m.id} className={`mail-item ${m.folder === 'sent' ? 'is-sent' : ''}`}>
            <span className="mail-dot" aria-hidden="true">
              <Icon name={m.folder === 'sent' ? 'arrowUpRight' : 'inbox'} size={16} />
            </span>
            <details className="mail-card">
              <summary>
                <span className="mail-head">
                  <strong>{m.folder === 'sent' ? 'Wysłano' : senderLabel(m)}</strong>
                  <span className="mail-time">{timeAgo(m.received_at)}</span>
                </span>
                <span className="mail-subject">{m.subject}</span>
                {m.classification_summary && (
                  <span className="mail-ai">
                    <Icon name="sparkle" size={15} /> {m.classification_summary}
                  </span>
                )}
              </summary>
              <p className="mail-body">{m.body}</p>
            </details>
          </li>
        ))}
      </ol>
    </section>
  )
}

function DoneStep({ app }: { app: Application }) {
  const cancelled = app.status === 'cancelled'
  return (
    <section className="card stack" aria-labelledby="done-h">
      <h2 id="done-h">{cancelled ? 'Wniosek anulowany' : 'Wniosek złożony'}</h2>
      {cancelled ? (
        <p>Ten wniosek został anulowany i nic z niego nie zostało wysłane.</p>
      ) : (
        <>
          <p>
            Status: <strong>{STATUS_LABEL[app.status]}</strong>
            {app.sent_at && <span className="muted"> · {formatDateTime(app.sent_at)}</span>}
          </p>
          {app.channel === 'employer_email' && app.recipient_domain && (
            <p>
              Wysłaliśmy go do pracodawcy (adres w domenie <strong>{app.recipient_domain}</strong>). Kopię znajdziesz w poczcie.
            </p>
          )}
          {app.channel === 'portal_agent' && <p>Złożyliśmy go przez formularz online. Odpowiedź urzędu pokaże się tutaj.</p>}
          {app.channel === 'pdf_download' && (
            <p>
              {app.recipient_domain === 'zus.pl'
                ? 'Złożyliśmy go w ZUS przez eZUS (symulacja). Odpowiedź urzędu pokaże się tutaj.'
                : app.recipient_domain
                  ? 'Złożyliśmy go w elektronicznej skrzynce urzędu (symulacja). Odpowiedź pokaże się tutaj.'
                  : 'Wniosek jest złożony. Zachowaj PDF na wypadek pytań z urzędu.'}
            </p>
          )}
          <div className="row">
            <Button to="/kalendarz" leading="calendar" variant="secondary">
              Zobacz w kalendarzu
            </Button>
          </div>
        </>
      )}
      <Link to="/wnioski">Wróć do listy wniosków</Link>
    </section>
  )
}

function ReadOnlyView({ app, applicantName }: { app: Application; applicantName: string }) {
  const shown = app.fields.filter((f) => app.values[f.id] !== undefined && app.values[f.id] !== null && app.values[f.id] !== '')
  return (
    <section className="card stack" aria-labelledby="ro-h">
      <h2 id="ro-h">Wniosek składa {applicantName}</h2>
      <p className="muted">Możesz go tylko przeglądać. Status: {STATUS_LABEL[app.status]}.</p>
      <dl className="facts">
        {shown.map((f) => (
          <div key={f.id} style={{ display: 'contents' }}>
            <dt>{f.label}</dt>
            <dd>{f.type === 'bool' ? (app.values[f.id] === true ? 'Tak' : 'Nie') : String(app.values[f.id])}</dd>
          </div>
        ))}
      </dl>
      <Link to="/wnioski">Wróć do listy wniosków</Link>
    </section>
  )
}

export default function ApplicationWizard({ applicationId }: { applicationId: string }) {
  const { user, family } = useSession()
  const [app, setApp] = useState<Application | null>(null)
  const [forms, setForms] = useState<FormEntry[]>([])
  const [error, setError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [stage, setStage] = useState<'preview' | 'send'>('preview')
  // wniosek zniknął (usunięty albo dane po stronie serwera zostały odświeżone) — zamiast błędu pokazujemy drogę dalej
  const [gone, setGone] = useState(false)
  const markGone = useCallback(() => setGone(true), [])

  useEffect(() => {
    let cancelled = false
    api<Application>(`/api/applications/${applicationId}`)
      .then((a) => !cancelled && setApp(a))
      .catch((e) => {
        if (cancelled) return
        if (e instanceof ApiError && e.status === 404) setGone(true)
        else setError(errText(e, 'Nie udało się wczytać wniosku.'))
      })
    api<FormsResponse>('/api/applications/forms')
      .then((f) => !cancelled && setForms(f.forms))
      .catch(() => undefined) // katalog służy tylko do wyboru kanału — kreator działa bez niego
    return () => {
      cancelled = true
    }
  }, [applicationId])

  /** Wykonuje zapis wniosku; odpowiedź API (przeliczony wniosek) zastępuje stan. */
  const run = useCallback(async (action: () => Promise<Application>, fallback: string) => {
    setBusy(true)
    setActionError(null)
    try {
      setApp(await action())
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setGone(true)
      else setActionError(errText(e, fallback))
    } finally {
      setBusy(false)
    }
  }, [])

  const answer = useCallback(
    (fieldId: string, value: AnswerValue) =>
      run(
        () => api<Application>(`/api/applications/${applicationId}/answers`, { method: 'POST', body: { answers: { [fieldId]: value } } }),
        'Nie udało się zapisać odpowiedzi.',
      ),
    [applicationId, run],
  )
  const edit = useCallback(
    (fieldId: string, value: AnswerValue) =>
      run(
        () => api<Application>(`/api/applications/${applicationId}`, { method: 'PATCH', body: { values: { [fieldId]: value } } }),
        'Nie udało się zapisać zmiany.',
      ),
    [applicationId, run],
  )
  const changeChannel = useCallback(
    (channel: Channel) =>
      run(() => api<Application>(`/api/applications/${applicationId}`, { method: 'PATCH', body: { channel } }), 'Nie udało się zmienić sposobu złożenia.'),
    [applicationId, run],
  )

  if (gone) {
    return (
      <div className="page page-narrow">
        <PageHeader title="Tego wniosku już nie ma" eyebrow="Wniosek" back="/wnioski" />
        <div className="card empty stack" role="status">
          <Icon name="doc" size={36} />
          <p>
            Mógł zostać usunięty albo dane po naszej stronie zostały odświeżone. Zacznij od nowa, a formularz wypełnimy za
            Ciebie jeszcze raz.
          </p>
          <div className="row" style={{ justifyContent: 'center' }}>
            <Button to="/wnioski" variant="secondary" leading="arrowLeft">
              Wróć do wniosków
            </Button>
            <Button to={app ? `/wnioski/nowy?form=${encodeURIComponent(app.form_code)}` : '/wnioski/nowy'} leading="plus">
              Nowy wniosek
            </Button>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <p role="alert" className="alert">
        {error}
      </p>
    )
  }
  if (!app) return <p role="status">Ładowanie wniosku…</p>

  const form = forms.find((f) => f.code === app.form_code)
  const title = form?.name ?? app.form_code
  const step: StepKey = isFinal(app.status) ? 'done' : app.missing.length > 0 ? 'data' : stage
  const applicant = family?.members.find((m) => m.id === app.applicant_id)

  return (
    <div className="page page-narrow wizard">
      <PageHeader title={SHORT[app.form_code] ?? title} eyebrow={form?.institution ?? 'Wniosek'} back="/wnioski">
        {SHORT[app.form_code] && <p className="muted small" style={{ margin: 0 }}>{title}</p>}
        <div className="row" style={{ gap: '0.4rem', marginTop: '0.4rem' }}>
          <Pill tone={STATUS_TONE[app.status]} dot>
            {STATUS_LABEL[app.status]}
          </Pill>
          <Pill>
            <Icon name={app.channel === 'portal_agent' ? 'globe' : 'doc'} size={14} /> {CHANNEL_SHORT[app.channel]}
          </Pill>
          {form?.deadline && <Pill tone="amber">Termin: {/^\d{4}-\d{2}-\d{2}$/.test(form.deadline) ? formatDate(form.deadline) : form.deadline}</Pill>}
        </div>
      </PageHeader>
      {step !== 'done' && <Stepper current={step} />}

      {user && app.applicant_id !== user.id && !isFinal(app.status) ? (
        <ReadOnlyView app={app} applicantName={applicant?.name ?? 'drugi rodzic'} />
      ) : (
        <>
          {step === 'data' && <MissingFieldsStep questions={app.missing} onAnswer={answer} busy={busy} error={actionError} />}
          {step === 'preview' && (
            <PreviewStep
              app={app}
              form={form}
              busy={busy}
              error={actionError}
              onEdit={edit}
              onChannel={changeChannel}
              onNext={() => setStage('send')}
            />
          )}
          {step === 'send' && (
            <>
              <SendStep app={app} onChange={setApp} onGone={markGone} />
              {app.channel !== 'portal_agent' && (
                <div className="row">
                  <button style={{
                    marginTop: '1rem',
                  }} type="button" className="btn btn-secondary" onClick={() => setStage('preview')}>
                    Wróć do podglądu
                  </button>
                </div>
              )}
            </>
          )}
          {step === 'done' && <DoneStep app={app} />}
        </>
      )}
      <Correspondence appId={app.id} />
    </div>
  )
}
