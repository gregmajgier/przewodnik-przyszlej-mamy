import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import { useSession } from '../../lib/session'
import { isFinal, STATUS_LABEL } from './types'
import type { Application, FormsResponse } from './types'
import './applications.css'

const formatWhen = (iso: string) => new Date(iso).toLocaleDateString('pl-PL', { dateStyle: 'medium' })

export default function ApplicationsPage() {
  const { family, user, loading } = useSession()
  const [apps, setApps] = useState<Application[] | null>(null)
  const [catalog, setCatalog] = useState<FormsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!family) return
    let cancelled = false
    api<Application[]>('/api/applications')
      .then((a) => !cancelled && setApps(a))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.detail : 'Nie udało się wczytać wniosków.'))
    api<FormsResponse>('/api/applications/forms')
      .then((f) => !cancelled && setCatalog(f))
      .catch(() => undefined) // bez katalogu pokazujemy kody wniosków
    return () => {
      cancelled = true
    }
  }, [family])

  if (loading) return <p role="status">Ładowanie…</p>
  if (!family) return <Navigate to="/start" replace />

  const nameOf = (code: string) => catalog?.forms.find((f) => f.code === code)?.name ?? code
  const memberName = (id: string) => (id === user?.id ? 'Ty' : (family.members.find((m) => m.id === id)?.name ?? 'drugi rodzic'))
  const childName = (id: string | null) => family.children.find((c) => c.id === id)?.name
  const flow = catalog?.recommended_flow ?? []

  return (
    <div className="stack">
      <div className="row apps-head">
        <h1>Wnioski</h1>
        <Link className="btn" to="/wnioski/nowy">
          Nowy wniosek
        </Link>
      </div>

      {flow.length > 0 && (
        <section className="notice" aria-label="Polecana kolejność">
          <strong>Polecana kolejność:</strong>{' '}
          {flow.map((code, i) => (
            <span key={code}>
              {i > 0 && ' → '}
              <Link to={`/wnioski/nowy?form=${encodeURIComponent(code)}`}>{nameOf(code)}</Link>
            </span>
          ))}
        </section>
      )}

      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {!apps && !error && <p role="status">Wczytuję wnioski…</p>}
      {apps && apps.length === 0 && <p className="muted">Nie macie jeszcze żadnych wniosków. Zacznij od „Nowy wniosek”.</p>}

      {apps && apps.length > 0 && (
        <ul className="app-list">
          {apps.map((a) => (
            <li key={a.id} className="app-item">
              <div>
                <Link to={`/wnioski/${a.id}`}>
                  <strong>{nameOf(a.form_code)}</strong>
                </Link>
                <div className="muted">
                  {childName(a.child_id) && <>dziecko: {childName(a.child_id)} · </>}
                  składa: {memberName(a.applicant_id)} · {formatWhen(a.created_at)}
                </div>
              </div>
              <span className={`status-pill is-${a.status}`}>{STATUS_LABEL[a.status]}</span>
              <Link className="btn btn-secondary" to={`/wnioski/${a.id}`}>
                {isFinal(a.status) ? 'Zobacz' : 'Kontynuuj'}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
