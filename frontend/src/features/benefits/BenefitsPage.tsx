import { useCallback, useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import { useSession } from '../../lib/session'
import BenefitCard from './BenefitCard'
import type { BenefitMatch } from './types'
import './benefits.css'

export default function BenefitsPage() {
  const { family, loading } = useSession()
  const [items, setItems] = useState<BenefitMatch[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  useEffect(() => {
    if (!family) return
    let cancelled = false
    api<BenefitMatch[]>('/api/benefits')
      .then((data) => !cancelled && setItems(data))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.detail : 'Nie udało się wczytać świadczeń.'))
    return () => {
      cancelled = true
    }
  }, [family])

  const answer = useCallback(async (benefitId: string, conditionId: string, value: boolean) => {
    setBusyId(benefitId)
    setError(null)
    try {
      // odpowiedź zapisuje się w profilu (nie pytamy drugi raz); w odpowiedzi jest przeliczone dopasowanie
      const updated = await api<BenefitMatch>(`/api/benefits/${benefitId}/answers`, {
        method: 'POST',
        body: { condition_id: conditionId, answer: value },
      })
      setItems((prev) => prev?.map((m) => (m.benefit.id === benefitId ? updated : m)) ?? prev)
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Nie udało się zapisać odpowiedzi.')
    } finally {
      setBusyId(null)
    }
  }, [])

  if (loading) return <p role="status">Ładowanie…</p>
  if (!family) return <Navigate to="/start" replace />

  const fits = items?.filter((m) => m.match.status === 'fits') ?? []
  const maybe = items?.filter((m) => m.match.status === 'maybe') ?? []
  const rest = items?.filter((m) => m.match.status === 'no') ?? []

  return (
    <div className="stack">
      <h1>Świadczenia dla Waszej rodziny</h1>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {!items && !error && <p role="status">Wczytuję świadczenia…</p>}

      {items && (
        <>
          <section className="stack" aria-labelledby="fits-h">
            <h2 id="fits-h">Pasuje ({fits.length})</h2>
            {fits.length === 0 && <p className="muted">Na razie nic nie pasuje na pewno — zajrzyj niżej.</p>}
            <div className="benefit-grid">
              {fits.map((m) => (
                <BenefitCard key={m.benefit.id} item={m} onAnswer={answer} busy={busyId === m.benefit.id} />
              ))}
            </div>
          </section>

          <section className="stack" aria-labelledby="maybe-h">
            <h2 id="maybe-h">Może ci przysługiwać ({maybe.length})</h2>
            {maybe.length > 0 && <p className="muted">Odpowiedz na kilka pytań — zapamiętamy to i nie zapytamy drugi raz.</p>}
            <div className="benefit-grid">
              {maybe.map((m) => (
                <BenefitCard key={m.benefit.id} item={m} onAnswer={answer} busy={busyId === m.benefit.id} />
              ))}
            </div>
          </section>

          {rest.length > 0 && (
            <details className="benefit-rest">
              <summary>Pokaż pozostałe ({rest.length})</summary>
              <div className="benefit-grid">
                {rest.map((m) => (
                  <BenefitCard key={m.benefit.id} item={m} onAnswer={answer} />
                ))}
              </div>
            </details>
          )}
        </>
      )}
    </div>
  )
}
