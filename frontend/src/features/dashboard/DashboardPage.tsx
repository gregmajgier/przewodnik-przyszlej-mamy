import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import { formatDate, formatPln } from '../../lib/format'
import { useSession } from '../../lib/session'
import type { Summary } from '../benefits/types'
import { getDashboardWidgets } from './widgets'
import './dashboard.css'

/** Fragment `GET /api/parametry` — pokazujemy tylko to, co jest w odpowiedzi. */
interface Parametry {
  zasilek_macierzynski_procent?: Record<string, number>
  swiadczenie_rodzicielskie_zl_mies?: number
  becikowe_zl?: number
  za_zyciem_zl?: number
}

const percent = (n: number) => `${String(n).replace('.', ',')}%`

function Rates({ p }: { p: Parametry }) {
  const pct = p.zasilek_macierzynski_procent
  const rows: [string, string][] = []
  if (pct?.macierzynski !== undefined) rows.push(['Zasiłek macierzyński', percent(pct.macierzynski)])
  if (pct?.rodzicielski !== undefined) rows.push(['Urlop rodzicielski', percent(pct.rodzicielski)])
  if (pct?.jednolity_wniosek_21_dni !== undefined)
    rows.push(['Jeden wniosek w 21 dni po porodzie', percent(pct.jednolity_wniosek_21_dni)])
  if (p.swiadczenie_rodzicielskie_zl_mies !== undefined)
    rows.push(['Świadczenie rodzicielskie', `${formatPln(p.swiadczenie_rodzicielskie_zl_mies)} / mies.`])
  if (p.becikowe_zl !== undefined) rows.push(['Becikowe', formatPln(p.becikowe_zl)])
  if (p.za_zyciem_zl !== undefined) rows.push(['„Za życiem”', formatPln(p.za_zyciem_zl)])
  if (rows.length === 0) return null
  return (
    <dl className="facts dash-rates">
      {rows.map(([k, v]) => (
        <div key={k} style={{ display: 'contents' }}>
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  )
}

export default function DashboardPage() {
  const { user, family, loading } = useSession()
  const [summary, setSummary] = useState<Summary | null>(null)
  const [params, setParams] = useState<Parametry | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!family) return
    let cancelled = false
    api<Summary>('/api/summary')
      .then((s) => !cancelled && setSummary(s))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.detail : 'Nie udało się wczytać podsumowania.'))
    api<Parametry>('/api/parametry')
      .then((p) => !cancelled && setParams(p))
      .catch(() => undefined) // stawki to dodatek — panel działa bez nich
    return () => {
      cancelled = true
    }
  }, [family])

  if (loading) return <p role="status">Ładowanie…</p>
  if (user?.role === 'official') return <Navigate to="/urzednik" replace />
  if (!family) return <Navigate to="/start" replace />

  const firstName = user?.name.split(' ')[0] ?? ''
  const widgets = getDashboardWidgets()
  const total = summary ? summary.totals.fits + summary.totals.maybe : 0

  return (
    <div className="stack">
      <header className="dash-hero">
        <h1>Cześć{firstName ? `, ${firstName}` : ''}!</h1>
        {error && (
          <p role="alert" className="dash-alert">
            {error}
          </p>
        )}
        {!summary && !error && <p role="status">Liczę, co Wam przysługuje…</p>}
        {summary && (
          <dl className="dash-summary" aria-label="Podsumowanie">
            <div>
              <dt>Świadczeń dla rodziny</dt>
              <dd>{total}</dd>
            </div>
            <div>
              <dt>Szacunkowo rocznie</dt>
              <dd>{formatPln(summary.estimated_annual_total)}</dd>
            </div>
            <div>
              <dt>Najbliższy termin</dt>
              <dd>
                {summary.nearest_deadline ? (
                  <>
                    {formatDate(summary.nearest_deadline.date)}
                    <span className="dash-deadline-name">{summary.nearest_deadline.benefit_name}</span>
                  </>
                ) : (
                  'brak'
                )}
              </dd>
            </div>
          </dl>
        )}
      </header>

      <section className="dash-params card" aria-labelledby="params-h">
        <div className="row dash-params-head">
          <h2 id="params-h">Stawki</h2>
          <span className="params-label">{summary?.parameters_label ?? 'Parametry ZUS 2026 – aktywne'}</span>
        </div>
        {params ? <Rates p={params} /> : <p className="muted">Wczytuję stawki…</p>}
      </section>

      <div className="dash-grid">
        {widgets.map((w, i) => (
          <w.Component key={i} />
        ))}
      </div>
      {widgets.length === 0 && (
        <p className="muted">
          Tu pojawią się kafelki z Waszymi sprawami. <Link to="/swiadczenia">Zobacz świadczenia</Link>.
        </p>
      )}
    </div>
  )
}
