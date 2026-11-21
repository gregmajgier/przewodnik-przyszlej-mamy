import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../lib/api'
import type { BenefitMatch } from './types'
import './benefits.css'

const SHOWN = 3

export default function BenefitsWidget() {
  const [items, setItems] = useState<BenefitMatch[] | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    api<BenefitMatch[]>('/api/benefits')
      .then((r) => !cancelled && setItems(r))
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
    }
  }, [])

  const fits = items?.filter((i) => i.match.status === 'fits') ?? []
  const maybe = items?.filter((i) => i.match.status === 'maybe') ?? []

  return (
    <section className="bf-widget" aria-labelledby="bf-widget-h">
      <h2 id="bf-widget-h">Świadczenia</h2>
      {failed && <p className="muted">Nie udało się pobrać świadczeń. Spróbuj odświeżyć stronę.</p>}
      {!items && !failed && <p role="status">Ładowanie…</p>}
      {items && (
        <>
          <p>
            <strong>{fits.length} pasuje</strong> · {maybe.length} może przysługiwać
          </p>
          <ul>
            {fits.slice(0, SHOWN).map((i) => (
              <li key={i.benefit.id}>{i.benefit.name}</li>
            ))}
          </ul>
        </>
      )}
      <Link to="/swiadczenia">Wszystkie świadczenia</Link>
    </section>
  )
}
