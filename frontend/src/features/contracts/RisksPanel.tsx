import { useEffect, useState } from 'react'
import { api, ApiError } from '../../lib/api'
import { formatDate } from '../../lib/format'
import './contracts.css'
import type { Risk } from './types'

const SEVERITY_LABEL: Record<Risk['severity'], string> = {
  high: 'Pilne',
  medium: 'Ważne',
  info: 'Dobrze wiedzieć',
}

export function RiskList({ risks }: { risks: Risk[] }) {
  if (risks.length === 0) return <p className="muted">Brak ostrzeżeń. Wszystko wygląda dobrze.</p>
  return (
    <ul className="contract-list stack" aria-label="Ostrzeżenia">
      {risks.map((r) => (
        <li key={r.id} className={`risk risk-${r.severity}`}>
          <span className="risk-severity">{SEVERITY_LABEL[r.severity]}</span>
          <h3>{r.title}</h3>
          <p>{r.explanation}</p>
          {r.action && (
            <p>
              <strong>Co zrobić:</strong> {r.action}
              {r.deadline && <>, najlepiej do {formatDate(r.deadline)}</>}
            </p>
          )}
        </li>
      ))}
    </ul>
  )
}

/** Ostrzeżenia o ryzyku utraty świadczeń dla całej rodziny (`GET /api/risks`). */
export default function RisksPanel({ title = 'Na co uważać' }: { title?: string }) {
  const [risks, setRisks] = useState<Risk[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api<Risk[]>('/api/risks')
      .then((r) => !cancelled && setRisks(r))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.detail : 'Nie udało się pobrać ostrzeżeń.'))
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <section className="card stack" aria-labelledby="risks-h">
      <h2 id="risks-h">{title}</h2>
      {error ? (
        <p role="alert" className="alert">
          {error}
        </p>
      ) : risks === null ? (
        <p role="status">Ładowanie…</p>
      ) : (
        <RiskList risks={risks} />
      )}
    </section>
  )
}

/** Kafelek dashboardu. */
export function RisksWidget() {
  return <RisksPanel title="Ostrzeżenia" />
}
