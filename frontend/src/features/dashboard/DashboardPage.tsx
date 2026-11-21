import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { useSession } from '../../lib/session'
import { daysLeftPhrase, formatPln } from '../benefits/format'
import type { Summary } from '../benefits/types'
import { dashboardWidgets } from './widgets'
import './dashboard.css'

interface Params {
  zasilek_macierzynski_procent?: { macierzynski?: number; rodzicielski?: number; jednolity_wniosek_21_dni?: number }
  swiadczenie_rodzicielskie_zl_mies?: number
  becikowe_zl?: number
  za_zyciem_zl?: number
}

function pct(n: number): string {
  return `${String(n).replace('.', ',')}%`
}

function rates(p: Params): { label: string; value: string }[] {
  const out: { label: string; value: string }[] = []
  const z = p.zasilek_macierzynski_procent
  if (z?.macierzynski !== undefined && z.rodzicielski !== undefined) {
    const extra = z.jednolity_wniosek_21_dni !== undefined ? ` (${pct(z.jednolity_wniosek_21_dni)} przy jednym wniosku)` : ''
    out.push({ label: 'Zasiłek macierzyński / rodzicielski', value: `${pct(z.macierzynski)} / ${pct(z.rodzicielski)}${extra}` })
  }
  if (p.swiadczenie_rodzicielskie_zl_mies !== undefined)
    out.push({ label: 'Świadczenie rodzicielskie', value: `${formatPln(p.swiadczenie_rodzicielskie_zl_mies)} miesięcznie` })
  if (p.becikowe_zl !== undefined) out.push({ label: 'Becikowe', value: formatPln(p.becikowe_zl) })
  if (p.za_zyciem_zl !== undefined) out.push({ label: 'Za życiem', value: formatPln(p.za_zyciem_zl) })
  return out
}

export default function DashboardPage() {
  const { family, user } = useSession()
  const [summary, setSummary] = useState<Summary | null>(null)
  const [params, setParams] = useState<Params | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!family) return
    let cancelled = false
    api<Summary>('/api/summary')
      .then((s) => !cancelled && setSummary(s))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.detail : 'Nie udało się pobrać podsumowania.'))
    api<Params>('/api/parametry')
      .then((p) => !cancelled && setParams(p))
      .catch(() => undefined) // stawki są dodatkiem — panel działa bez nich
    return () => {
      cancelled = true
    }
  }, [family])

  if (!family) return <Navigate to="/start" replace />

  const firstName = user?.name.split(' ')[0] ?? ''
  const label = summary?.parameters_label ?? 'Parametry ZUS – aktywne'
  const count = summary ? summary.totals.fits + summary.totals.maybe : null

  return (
    <div className="db-page">
      <section className="db-hero" aria-labelledby="db-h">
        <h1 id="db-h">Cześć{firstName ? `, ${firstName}` : ''}! Oto wasza rodzina w pigułce.</h1>
        {error && (
          <p role="alert" className="db-alert">
            {error}
          </p>
        )}
        {!summary && !error && <p role="status">Liczymy…</p>}
        {summary && (
          <dl className="db-stats">
            <div>
              <dt>Świadczeń dla was</dt>
              <dd>
                <span className="db-num">{count}</span>
                <span className="db-sub">
                  {summary.totals.fits} pasuje · {summary.totals.maybe} może przysługiwać
                </span>
              </dd>
            </div>
            <div>
              <dt>Orientacyjnie rocznie</dt>
              <dd>
                <span className="db-num">{summary.estimated_annual_total > 0 ? formatPln(summary.estimated_annual_total) : '—'}</span>
              </dd>
            </div>
            <div>
              <dt>Najbliższy termin</dt>
              <dd>
                {summary.nearest_deadline ? (
                  <>
                    <span className="db-num db-num-sm">{summary.nearest_deadline.name}</span>
                    <span className="db-sub">
                      {formatDate(summary.nearest_deadline.date)} · {daysLeftPhrase(summary.nearest_deadline.days_left)}
                    </span>
                  </>
                ) : (
                  <span className="db-num db-num-sm">brak</span>
                )}
              </dd>
            </div>
          </dl>
        )}
        <p className="db-label">
          <span className="db-pill">{label}</span>
        </p>
      </section>

      {summary && summary.warnings.length > 0 && (
        <section className="db-warnings" aria-label="Ostrzeżenia">
          <ul>
            {summary.warnings.map((w) => (
              <li key={w}>
                <span aria-hidden="true">⚠ </span>
                {w}
              </li>
            ))}
          </ul>
        </section>
      )}

      {params && rates(params).length > 0 && (
        <section className="db-rates" aria-label="Stawki">
          <ul>
            {rates(params).map((r) => (
              <li key={r.label}>
                <span className="muted">{r.label}</span> <strong>{r.value}</strong>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="db-grid">
        {[...dashboardWidgets].sort((a, b) => a.order - b.order).map((w, i) => (
          <div className="db-tile" key={i}>
            <w.Component />
          </div>
        ))}
      </div>
      <p className="muted">
        Pełną listę z uzasadnieniem znajdziesz w <Link to="/swiadczenia">Świadczeniach</Link>.
      </p>
    </div>
  )
}
