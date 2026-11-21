import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../lib/api'
import { isFinal, STATUS_LABEL } from './types'
import type { Application, FormsResponse } from './types'
import '../benefits/benefits.css'

const TOP = 3

export default function ApplicationsWidget() {
  const [apps, setApps] = useState<Application[] | null>(null)
  const [catalog, setCatalog] = useState<FormsResponse | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    api<Application[]>('/api/applications')
      .then((a) => !cancelled && setApps(a))
      .catch(() => !cancelled && setFailed(true))
    api<FormsResponse>('/api/applications/forms')
      .then((f) => !cancelled && setCatalog(f))
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [])

  const open = apps?.filter((a) => !isFinal(a.status)) ?? []
  const nameOf = (code: string) => catalog?.forms.find((f) => f.code === code)?.name ?? code

  return (
    <section className="widget-card" aria-labelledby="w-apps-h">
      <h2 id="w-apps-h">Wnioski</h2>
      {failed && <p className="muted">Nie udało się wczytać wniosków.</p>}
      {!apps && !failed && <p role="status" className="muted">Ładowanie…</p>}
      {apps && (
        <>
          {open.length === 0 ? (
            <p className="muted">Nie masz rozpoczętych wniosków.</p>
          ) : (
            <ul className="widget-list">
              {open.slice(0, TOP).map((a) => (
                <li key={a.id}>
                  <Link to={`/wnioski/${a.id}`}>{nameOf(a.form_code)}</Link> <span className="muted">— {STATUS_LABEL[a.status]}</span>
                </li>
              ))}
            </ul>
          )}
          <Link className="btn btn-secondary" to="/wnioski/nowy">
            Nowy wniosek
          </Link>
        </>
      )}
    </section>
  )
}
