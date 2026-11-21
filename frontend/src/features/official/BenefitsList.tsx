import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import './official.css'
import { STATUS_LABEL } from './types'
import type { OfficialBenefit } from './types'

export default function BenefitsList() {
  const [items, setItems] = useState<OfficialBenefit[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api<OfficialBenefit[]>('/api/official/benefits')
      .then((r) => !cancelled && setItems(r))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.detail : 'Nie udało się pobrać świadczeń.'))
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h1>Świadczenia Twojej jednostki</h1>
        <Link className="btn" to="/urzednik/swiadczenia/nowe">
          Dodaj świadczenie
        </Link>
      </div>
      <p className="muted">
        Opublikowane świadczenia widzą rodzice z obszaru Twojej jednostki. Mieszkańcy województwa
        widzą świadczenia wojewódzkie we wszystkich gminach.
      </p>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {items === null && !error && <p role="status">Ładowanie…</p>}
      {items?.length === 0 && <p className="muted">Nie dodano jeszcze żadnego świadczenia.</p>}
      {items && items.length > 0 && (
        <ul className="plain-list stack">
          {items.map((b) => (
            <li key={b.id} className="card row" style={{ justifyContent: 'space-between' }}>
              <div>
                <Link to={`/urzednik/swiadczenia/${b.id}`}>
                  <strong>{b.name}</strong>
                </Link>
                <div className="muted">{b.amount_text}</div>
              </div>
              <span className={`status-pill status-${b.status}`}>{STATUS_LABEL[b.status]}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
