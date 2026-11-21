import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Logo } from '../../components/Logo'
import { api, ApiError } from '../../lib/api'
import { formatPln } from '../benefits/format'
import type { Analysis } from '../benefits/types'
import './analysis.css'

const STEP_DELAY_MS = 700

function prefersReducedMotion(): boolean {
  try {
    return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  } catch {
    return false
  }
}

export default function AnalysisPage() {
  const navigate = useNavigate()
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [error, setError] = useState<string | null>(null)
  /** ile kroków jest ukończonych; krok o tym indeksie jest właśnie „liczony” */
  const [done, setDone] = useState(0)

  useEffect(() => {
    let cancelled = false
    api<Analysis>('/api/analysis')
      .then((a) => {
        if (cancelled) return
        setAnalysis(a)
        if (prefersReducedMotion()) setDone(a.steps.length)
      })
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.detail : 'Nie udało się przeprowadzić analizy.'))
    return () => {
      cancelled = true
    }
  }, [])

  const total = analysis?.steps.length ?? 0
  useEffect(() => {
    if (!analysis || done >= total) return
    const t = setTimeout(() => setDone((d) => d + 1), STEP_DELAY_MS)
    return () => clearTimeout(t)
  }, [analysis, done, total])

  if (error) {
    return (
      <div className="an-panel">
        <p role="alert" className="an-error">
          {error}
        </p>
        <button type="button" className="an-cta" onClick={() => navigate('/')}>
          Przejdź do panelu
        </button>
      </div>
    )
  }
  if (!analysis) {
    return (
      <div className="an-panel">
        <p role="status">Poznajemy waszą rodzinę…</p>
      </div>
    )
  }

  const finished = done >= total
  const visible = analysis.steps.slice(0, Math.min(done + 1, total))

  return (
    <div className="an-panel">
      <Logo className="an-logo" animate={false} color="currentColor" />
      <h1>Poznajemy waszą rodzinę…</h1>
      <ol className="an-steps" aria-live="polite">
        {visible.map((s, i) => {
          const complete = i < done
          const mark = !complete ? '⟳' : s.status === 'warning' ? '⚠' : '✓'
          return (
            <li key={s.key} data-testid={`step-${s.key}`} className={complete ? 'an-done' : 'an-working'}>
              <span className="an-mark" aria-hidden="true">
                {mark}
              </span>
              <span>
                <strong>{s.label}:</strong> {s.detail}
              </span>
            </li>
          )
        })}
      </ol>
      {finished && (
        <div className="an-result">
          <p className="an-big">
            Pasuje do was: <strong>{analysis.totals.fits}</strong> · może przysługiwać:{' '}
            <strong>{analysis.totals.maybe}</strong>
          </p>
          {analysis.estimated_annual_total > 0 && (
            <p>
              Orientacyjnie około <strong>{formatPln(analysis.estimated_annual_total)}</strong> rocznie.
            </p>
          )}
          <button type="button" className="an-cta" onClick={() => navigate('/')}>
            Przejdź do panelu
          </button>
        </div>
      )}
    </div>
  )
}
