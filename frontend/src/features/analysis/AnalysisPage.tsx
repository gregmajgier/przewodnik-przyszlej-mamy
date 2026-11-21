import { useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { Logo } from '../../components/Logo'
import { api, ApiError } from '../../lib/api'
import { prefersReducedMotion } from '../../lib/motion'
import { useSession } from '../../lib/session'
import type { Analysis } from '../benefits/types'
import '../../components/a11y.css'
import './analysis.css'

/** Odstęp między kolejnymi krokami „analizy” (ms). */
export const STEP_MS = 700

export default function AnalysisPage() {
  const { family, loading } = useSession()
  const navigate = useNavigate()
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [error, setError] = useState<string | null>(null)
  // tick = liczba ukończonych kroków; krok o indeksie `tick` jest w toku (⟳), kolejne jeszcze ukryte
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

  if (loading) return <p role="status">Ładowanie…</p>
  if (!family) return <Navigate to="/start" replace />

  const finished = analysis !== null && tick >= total

  return (
    <div className="analysis stack">
      <div className="analysis-hero">
        <Logo className="analysis-logo" />
        <h1>Sprawdzam, co Wam przysługuje</h1>
        <p>Chwilkę — czytam Wasze dane i porównuję je z listą świadczeń.</p>
      </div>

      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {!analysis && !error && <p role="status">Przygotowuję analizę…</p>}

      {analysis && (
        <ol className="analysis-steps" aria-live="polite" aria-label="Postęp analizy">
          {analysis.steps.slice(0, tick + 1).map((step, i) => {
            const done = i < tick
            return (
              <li key={step.key} className={done ? 'is-done' : 'is-active'}>
                <span className="analysis-mark" aria-hidden="true">
                  {done ? '✓' : '⟳'}
                </span>
                <span>
                  <strong>{step.label}</strong>
                  <span className="muted analysis-detail">{done ? step.detail : 'W toku…'}</span>
                </span>
                <span className="sr-only">{done ? 'gotowe' : 'w toku'}</span>
              </li>
            )
          })}
        </ol>
      )}

      {finished && analysis && (
        <section className="analysis-result" aria-label="Wynik analizy">
          <p className="analysis-total">
            <strong>{analysis.totals.fits}</strong> pasuje · <strong>{analysis.totals.maybe}</strong> może ci
            przysługiwać · <strong>{analysis.totals.no}</strong> nie pasuje
          </p>
          <button type="button" className="btn" onClick={() => navigate('/')}>
            Przejdź do panelu
          </button>
        </section>
      )}
    </div>
  )
}
