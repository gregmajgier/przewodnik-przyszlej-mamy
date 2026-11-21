import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import { useSession } from '../../lib/session'
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
          <span className="stepper-n">{i + 1}</span> {s.label}
        </li>
      ))}
    </ol>
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
          {app.channel === 'portal_agent' && <p>Złożyliśmy go w makiecie portalu (symulacja).</p>}
          {app.channel === 'pdf_download' && <p>Oznaczyliśmy go jako złożony samodzielnie.</p>}
          <div className="row">
            <Link className="btn" to="/kalendarz">
              Zobacz w kalendarzu
            </Link>
            <Link className="btn btn-secondary" to="/poczta">
              Zobacz pocztę
            </Link>
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

  useEffect(() => {
    let cancelled = false
    api<Application>(`/api/applications/${applicationId}`)
      .then((a) => !cancelled && setApp(a))
      .catch((e) => !cancelled && setError(errText(e, 'Nie udało się wczytać wniosku.')))
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
      setActionError(errText(e, fallback))
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
    <div className="stack wizard">
      <h1>{title}</h1>
      <Stepper current={step} />

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
              <SendStep app={app} onChange={setApp} />
              {app.channel !== 'portal_agent' && (
                <div className="row">
                  <button type="button" className="btn btn-secondary" onClick={() => setStage('preview')}>
                    Wróć do podglądu
                  </button>
                </div>
              )}
            </>
          )}
          {step === 'done' && <DoneStep app={app} />}
        </>
      )}
    </div>
  )
}
