import { useCallback, useEffect, useMemo, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import { useSession } from '../../lib/session'
import type { FormEntry, FormsResponse } from '../applications/types'
import BenefitCard from './BenefitCard'
import type { BenefitMatch } from './types'
import '../../components/a11y.css'
import './benefits.css'

type Sort = 'default' | 'amount'

/** Uzasadnienia, które powtarzają się w większości kart grupy (np. „w rodzinie jest dziecko w drodze”) — pokazujemy raz. */
function commonReasons(group: BenefitMatch[]): string[] {
  if (group.length < 3) return []
  const counts = new Map<string, number>()
  for (const m of group) for (const r of new Set(m.match.reasons)) counts.set(r, (counts.get(r) ?? 0) + 1)
  return [...counts].filter(([, n]) => n >= Math.ceil(group.length * 0.6)).map(([r]) => r)
}

function sortGroup(group: BenefitMatch[], sort: Sort): BenefitMatch[] {
  if (sort === 'default') return group
  return [...group].sort((a, b) => (b.benefit.annual_value_estimate ?? 0) - (a.benefit.annual_value_estimate ?? 0))
}

export default function BenefitsPage() {
  const { family, loading } = useSession()
  const [items, setItems] = useState<BenefitMatch[] | null>(null)
  const [forms, setForms] = useState<FormEntry[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [sort, setSort] = useState<Sort>('default')

  useEffect(() => {
    if (!family) return
    let cancelled = false
    api<BenefitMatch[]>('/api/benefits')
      .then((data) => !cancelled && setItems(data))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.detail : 'Nie udało się wczytać świadczeń.'))
    api<FormsResponse>('/api/applications/forms')
      .then((f) => !cancelled && setForms(f.forms))
      .catch(() => undefined) // bez katalogu wniosków przyciski mają ogólny podpis
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

  const fits = useMemo(() => sortGroup(items?.filter((m) => m.match.status === 'fits') ?? [], sort), [items, sort])
  const maybe = useMemo(() => sortGroup(items?.filter((m) => m.match.status === 'maybe') ?? [], sort), [items, sort])
  const rest = useMemo(() => items?.filter((m) => m.match.status === 'no') ?? [], [items])
  const fitsCommon = useMemo(() => commonReasons(fits), [fits])
  const maybeCommon = useMemo(() => commonReasons(maybe), [maybe])
  const anyVerify = items?.some((m) => m.benefit.verify) ?? false

  if (loading) return <p role="status">Ładowanie…</p>
  if (!family) return <Navigate to="/start" replace />

  return (
    <div className="stack">
      <div className="row benefits-head">
        <h1>Świadczenia dla Waszej rodziny</h1>
        {items && items.length > 1 && (
          <div className="field benefits-sort">
            <label htmlFor="benefits-sort">Sortuj</label>
            <select id="benefits-sort" value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
              <option value="default">Domyślnie</option>
              <option value="amount">Najwyższa kwota roczna</option>
            </select>
          </div>
        )}
      </div>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {!items && !error && <p role="status">Wczytuję świadczenia…</p>}
      {anyVerify && (
        <p className="muted benefits-verify-note">
          Część kwot i warunków jest oznaczona jako „do weryfikacji”. Sprawdź je w źródle (przycisk „Źródło”) przed
          złożeniem wniosku.
        </p>
      )}

      {items && (
        <>
          <section className="stack" aria-labelledby="fits-h">
            <h2 id="fits-h">Pasuje ({fits.length})</h2>
            {fitsCommon.length > 0 && <p className="muted benefits-common">Dlaczego pasują: {fitsCommon.join('; ')}.</p>}
            {fits.length === 0 && <p className="muted">Na razie nic nie pasuje na pewno. Zajrzyj niżej.</p>}
            <div className="benefit-grid">
              {fits.map((m) => (
                <BenefitCard key={m.benefit.id} item={m} onAnswer={answer} busy={busyId === m.benefit.id} forms={forms} hideReasons={fitsCommon} />
              ))}
            </div>
          </section>

          <section className="stack" aria-labelledby="maybe-h">
            <h2 id="maybe-h">Może ci przysługiwać ({maybe.length})</h2>
            {maybe.length > 0 && <p className="muted">Odpowiedz na kilka pytań. Zapamiętamy to i nie zapytamy drugi raz.</p>}
            {maybeCommon.length > 0 && <p className="muted benefits-common">Dlaczego: {maybeCommon.join('; ')}.</p>}
            <div className="benefit-grid">
              {maybe.map((m) => (
                <BenefitCard key={m.benefit.id} item={m} onAnswer={answer} busy={busyId === m.benefit.id} forms={forms} hideReasons={maybeCommon} />
              ))}
            </div>
          </section>

          {rest.length > 0 && (
            <details className="benefit-rest">
              <summary>Pokaż pozostałe ({rest.length})</summary>
              <div className="benefit-grid">
                {rest.map((m) => (
                  <BenefitCard key={m.benefit.id} item={m} onAnswer={answer} forms={forms} />
                ))}
              </div>
            </details>
          )}
        </>
      )}
    </div>
  )
}
