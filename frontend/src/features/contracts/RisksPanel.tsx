import { useEffect, useState } from 'react'
import { api, ApiError } from '../../lib/api'
import { formatDate } from '../../lib/format'
import './contracts.css'
import type { Risk } from './types'

const LABEL: Record<Risk['severity'], string> = { high: 'Ważne', medium: 'Uwaga', info: 'Informacja' }

export default function RisksPanel() {
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

  if (error)
    return (
      <p role="alert" className="alert">
        {error}
      </p>
    )
  if (!risks) return <p role="status">Ładowanie…</p>
  if (risks.length === 0) return <p className="muted">Brak ostrzeżeń. Dajemy znać, gdyby coś się zmieniło.</p>

  return (
    <ul className="risk-list">
      {risks.map((r) => (
        <li key={r.id} className="risk" data-severity={r.severity}>
          <span className="risk-label">{LABEL[r.severity]}</span>
          <h3>{r.title}</h3>
          <p>{r.explanation}</p>
          {r.action && (
            <p>
              <strong>Co zrobić:</strong> {r.action}
            </p>
          )}
          {r.deadline && (
            <p>
              <strong>Do kiedy:</strong> {formatDate(r.deadline)}
            </p>
          )}
        </li>
      ))}
    </ul>
  )
}
