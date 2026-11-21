import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { APP_STATUS_LABEL } from './types'
import type { MailThread } from './types'

function day(iso: string) {
  return formatDate(iso.slice(0, 10))
}

function Thread({ t }: { t: MailThread }) {
  const a = t.application
  return (
    <article className="card stack" aria-label={`Wniosek ${a.form_code}`}>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h2 style={{ margin: 0 }}>Wniosek {a.form_code}</h2>
        <span className="badge-sim" style={{ color: 'var(--fg)', borderColor: 'var(--fg)' }}>
          {APP_STATUS_LABEL[a.status] ?? a.status}
        </span>
      </div>
      <p className="muted" style={{ margin: 0 }}>
        Złożył(a): {a.applicant_name}, {day(a.sent_at)} · do: {a.recipient_email ?? 'portal'}
      </p>
      {t.needs_review && (
        <p className="notice" style={{ margin: 0 }}>
          Nowa wiadomość w sprawie wniosku. Sprawdź ją, bo nie zmieniliśmy statusu automatycznie.
        </p>
      )}
      <ul className="stack" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {t.messages.map((m) => (
          <li key={m.id}>
            <details>
              <summary>
                <strong>{m.folder === 'sent' ? 'Wysłano' : m.from_addr}</strong>: {m.subject}{' '}
                <span className="muted">({day(m.received_at)})</span>
              </summary>
              <p style={{ whiteSpace: 'pre-line' }}>{m.body}</p>
              {m.classification_summary && (
                <p className="muted">
                  <span className="badge-sim">AI</span> {m.classification_summary}
                </p>
              )}
            </details>
          </li>
        ))}
      </ul>
    </article>
  )
}

export default function MailPage() {
  const [threads, setThreads] = useState<MailThread[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setThreads(await api<MailThread[]>('/api/mail/threads'))
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Nie udało się pobrać poczty.')
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    api<MailThread[]>('/api/mail/threads')
      .then((r) => !cancelled && setThreads(r))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.detail : 'Nie udało się pobrać poczty.'))
    return () => {
      cancelled = true
    }
  }, [])

  async function run(key: string, path: string, body?: unknown, message?: (r: Record<string, number>) => string) {
    setBusy(key)
    setError(null)
    setInfo(null)
    try {
      const r = await api<Record<string, number>>(path, { method: 'POST', body })
      if (message) setInfo(message(r))
      await load()
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Nie udało się wykonać operacji.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h1>Poczta ZUS / urzędy</h1>
        <Link to="/poczta/ustawienia">Ustawienia poczty</Link>
      </div>
      <p className="muted">
        Widzisz tylko korespondencję w sprawie Waszych wniosków. Odpowiedzi czyta asystent i sam
        aktualizuje status, gdy jest pewny, a inaczej poprosi Cię o sprawdzenie.
      </p>
      <div className="row">
        <button className="btn" type="button" disabled={busy !== null} onClick={() =>
          run('sync', '/api/mail/sync', undefined, (r) =>
            r.new_messages ? `Nowe wiadomości: ${r.new_messages}, zmiany statusu: ${r.status_changes}.` : 'Brak nowych wiadomości.')
        }>
          {busy === 'sync' ? 'Sprawdzam…' : 'Sprawdź pocztę'}
        </button>
        <button className="btn btn-secondary" type="button" disabled={busy !== null} onClick={() =>
          run('sim', '/api/mail/simulate-replies', undefined, (r) => `Dostarczono odpowiedzi: ${r.delivered}.`)
        }>
          Symuluj odpowiedzi
        </button>
        <span className="badge-sim">SYMULACJA</span>
      </div>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {info && (
        <p role="status" className="notice">
          {info}
        </p>
      )}
      {threads === null && !error && <p role="status">Ładowanie…</p>}
      {threads?.length === 0 && (
        <div className="card stack">
          <p className="muted">Nie wysłaliście jeszcze żadnego wniosku, więc nie ma tu korespondencji.</p>
          <div>
            <Link className="btn btn-secondary" to="/wnioski">
              Przejdź do wniosków
            </Link>
          </div>
        </div>
      )}
      {threads?.map((t) => <Thread key={t.application.id} t={t} />)}
    </div>
  )
}
