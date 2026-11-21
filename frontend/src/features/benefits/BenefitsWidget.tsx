import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../lib/api'
import type { BenefitMatch } from './types'
import './benefits.css'

const TOP = 4

export default function BenefitsWidget() {
  const [items, setItems] = useState<BenefitMatch[] | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    api<BenefitMatch[]>('/api/benefits')
      .then((data) => !cancelled && setItems(data))
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
    }
  }, [])

  const fits = items?.filter((m) => m.match.status === 'fits') ?? []
  const maybe = items?.filter((m) => m.match.status === 'maybe') ?? []

  return (
    <section className="widget-card" aria-labelledby="w-benefits-h">
      <h2 id="w-benefits-h">Świadczenia</h2>
      {failed && <p className="muted">Nie udało się wczytać świadczeń.</p>}
      {!items && !failed && <p role="status" className="muted">Ładowanie…</p>}
      {items && (
        <>
          <p className="muted">
            Pasuje {fits.length} · może ci przysługiwać {maybe.length}
          </p>
          <ul className="widget-list">
            {fits.slice(0, TOP).map((m) => (
              <li key={m.benefit.id}>
                <span>{m.benefit.name}</span>
                {m.benefit.amount_text && <span className="muted">: {m.benefit.amount_text}</span>}
              </li>
            ))}
          </ul>
          <Link to="/swiadczenia">Zobacz wszystkie świadczenia</Link>
        </>
      )}
    </section>
  )
}
