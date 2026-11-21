import { useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { Doodles } from '../../brand/Doodles'
import { Ribbons } from '../../brand/Ribbons'
import { BrandMark } from '../../brand/Splash'
import { api, ApiError } from '../../lib/api'
import { formatPln } from '../../lib/format'
import { prefersReducedMotion } from '../../lib/motion'
import { useSession } from '../../lib/session'
import { Button } from '../../ui/Button'
import { Icon } from '../../ui/Icon'
import type { IconName } from '../../ui/Icon'
import type { Analysis } from '../benefits/types'
import '../../brand/brand.css'
import '../../ui/ui.css'
import '../onboarding/flow.css'
import './analysis.css'

/** Odstęp między kolejnymi krokami „analizy” (ms). */
export const STEP_MS = 700

const STEP_ICONS: IconName[] = ['user', 'family', 'briefcase', 'search', 'pin', 'sparkle', 'checkCircle']

export default function AnalysisPage() {
  const { family, loading } = useSession()
  const navigate = useNavigate()
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [error, setError] = useState<string | null>(null)
  // tick = liczba ukończonych kroków; krok o indeksie `tick` jest w toku, kolejne jeszcze ukryte
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (!family) return
    let cancelled = false
    api<Analysis>('/api/analysis')
      .then((a) => {
        if (cancelled) return
        setAnalysis(a)
        if (prefersReducedMotion()) setTick(a.steps.length)
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof ApiError ? e.detail : 'Nie udało się przygotować analizy.')
      })
    return () => {
      cancelled = true
    }
  }, [family])

  const total = analysis?.steps.length ?? 0
  useEffect(() => {
    if (!analysis || tick >= total) return
    const id = window.setTimeout(() => setTick((t) => t + 1), STEP_MS)
    return () => window.clearTimeout(id)
  }, [analysis, tick, total])

  if (loading) return null
  if (!family) return <Navigate to="/start" replace />

  const finished = analysis !== null && tick >= total
  const count = analysis ? analysis.totals.fits + analysis.totals.maybe : 0

  return (
    <div className="flow flow-pink analysis">
      <Ribbons />
      {!finished && <Doodles set="analysis" opacity={0.35} />}
      <div className="flow-body flow-center">
        {!finished ? (
          <>
            <BrandMark className="analysis-brand" duration={1500} />
            <h1 className="flow-title">Sprawdzam, co Wam przysługuje</h1>
            <p className="flow-lead">Czytam Wasze dane i porównuję je z przepisami i bazą świadczeń.</p>
          </>
        ) : (
          analysis && (
            <section className="analysis-result" aria-label="Wynik analizy">
              <p className="analysis-eyebrow">Gotowe!</p>
              <p className="analysis-big">
                <span className="analysis-count">{count}</span>
                <span>świadczeń i ulg dla Was</span>
              </p>
              {analysis.estimated_annual_total > 0 && (
                <p className="analysis-sum">
                  szacunkowo <strong>{formatPln(analysis.estimated_annual_total)}</strong> w skali roku
                </p>
              )}
              <div className="analysis-chips">
                <span>
                  <Icon name="checkCircle" size={18} /> {analysis.totals.fits} pasuje
                </span>
                <span>
                  <Icon name="info" size={18} /> {analysis.totals.maybe} do sprawdzenia
                </span>
              </div>
              {analysis.nearest_deadline && (
                <p className="analysis-deadline">
                  <Icon name="clock" size={18} /> Najpilniejsze: {analysis.nearest_deadline.benefit_name}
                </p>
              )}
            </section>
          )
        )}

        {error && (
          <p role="alert" className="analysis-error">
            {error}
          </p>
        )}
        {!analysis && !error && (
          <p role="status" className="sr-only">
            Przygotowuję analizę…
          </p>
        )}

        {analysis && !finished && (
          <ol className="analysis-steps" aria-live="polite" aria-label="Postęp analizy">
            {analysis.steps.slice(0, tick + 1).map((step, i) => {
              const done = i < tick
              return (
                <li key={step.key} className={done ? 'is-done' : 'is-active'}>
                  <span className="analysis-mark" aria-hidden="true">
                    {done ? <Icon name="check" size={18} stroke={2.4} /> : <Icon name={STEP_ICONS[i % STEP_ICONS.length]} size={18} />}
                  </span>
                  <span className="analysis-text">
                    <strong>{step.label}</strong>
                    <span className="analysis-detail">{done ? step.detail : 'W toku…'}</span>
                  </span>
                  <span className="sr-only">{done ? 'gotowe' : 'w toku'}</span>
                </li>
              )
            })}
          </ol>
        )}
      </div>
      {finished && (
        <div className="flow-foot">
          <Button variant="white" block icon="arrowRight" onClick={() => navigate('/')}>
            Przejdź do panelu
          </Button>
        </div>
      )}
    </div>
  )
}
