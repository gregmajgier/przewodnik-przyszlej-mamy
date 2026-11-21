import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '../../lib/api'
import BenefitCard from './BenefitCard'
import type { BenefitMatch } from './types'
import './benefits.css'

function Group({ id, title, items, onAnswer, busy }: {
  id: string
  title: string
  items: BenefitMatch[]
  onAnswer: (b: string, c: string, a: boolean) => void
  busy: boolean
}) {
  return (
    <section className="bf-group" aria-labelledby={id}>
      <h2 id={id}>{title}</h2>
      <ul className="bf-list">
        {items.map((it) => (
          <li key={it.benefit.id}>
            <BenefitCard item={it} onAnswer={onAnswer} busy={busy} />
          </li>
        ))}
      </ul>
    </section>
  )
}

export default function BenefitsPage() {
  const [items, setItems] = useState<BenefitMatch[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showRest, setShowRest] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    api<BenefitMatch[]>('/api/benefits')
      .then((r) => !cancelled && setItems(r))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.detail : 'Nie udało się pobrać świadczeń.'))
    return () => {
      cancelled = true
    }
  }, [])

  const answer = useCallback(async (benefitId: string, conditionId: string, value: boolean) => {
    setBusy(true)
    setError(null)
    try {
      const updated = await api<BenefitMatch>(`/api/benefits/${benefitId}/answers`, {
        method: 'POST',
        body: { condition_id: conditionId, answer: value },
      })
      setItems((prev) => prev && prev.map((it) => (it.benefit.id === benefitId ? updated : it)))
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Nie udało się zapisać odpowiedzi.')
    } finally {
      setBusy(false)
    }
  }, [])

  if (error && !items) {
    return (
      <p role="alert" className="alert">
        {error}
      </p>
    )
  }
  if (!items) return <p role="status">Ładowanie świadczeń…</p>

  const fits = items.filter((i) => i.match.status === 'fits')
  const maybe = items.filter((i) => i.match.status === 'maybe')
  const rest = items.filter((i) => i.match.status === 'no')

  return (
    <div className="bf-page">
      <div className="bf-hero">
        <h1>Świadczenia dla waszej rodziny</h1>
        <p>Przy każdym pokazujemy, dlaczego pasuje — albo czego jeszcze brakuje.</p>
      </div>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {fits.length === 0 && maybe.length === 0 && (
        <p className="notice">Na razie nic nie pasuje — zajrzyj do pozostałych, żeby zobaczyć dlaczego.</p>
      )}
      {fits.length > 0 && <Group id="bf-fits" title="Pasuje do was" items={fits} onAnswer={answer} busy={busy} />}
      {maybe.length > 0 && (
        <Group id="bf-maybe" title="Może ci przysługiwać" items={maybe} onAnswer={answer} busy={busy} />
      )}
      {rest.length > 0 && (
        <div className="bf-more">
          <button
            type="button"
            className="btn btn-secondary"
            aria-expanded={showRest}
            aria-controls="bf-rest"
            onClick={() => setShowRest((v) => !v)}
          >
            {showRest ? 'Ukryj pozostałe' : `Pokaż pozostałe (${rest.length})`}
          </button>
          {showRest && (
            <div id="bf-rest">
              <Group id="bf-no" title="Nie pasuje (z powodem)" items={rest} onAnswer={answer} busy={busy} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
