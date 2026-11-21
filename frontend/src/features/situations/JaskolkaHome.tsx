import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import { formatDate } from '../../lib/format'
import type { FamilyView } from '../../lib/types'
import { fetchFoundations } from '../jaskolka/jaskolkaApi'
import type { Foundation } from '../jaskolka/jaskolkaApi'
import { canUndo, useFamilyMode } from './useFamilyMode'
import './situations.css'

interface BenefitRow {
  benefit: {
    id: string
    name: string
    description: string
    how_to_apply: string
    source_url: string
    form_codes: string[]
    tags: string[]
  }
  match: { status: 'fits' | 'maybe' | 'no' }
}

interface CalendarEvent {
  id: string
  title: string
  summary?: string
  due_date: string | null
  child_id: string | null
  done?: boolean
}

type Part<T> = { state: 'loading' } | { state: 'unavailable' } | { state: 'ok'; data: T }

/** Wczytuje część strony; błąd (np. funkcja jeszcze niedostępna) nie psuje reszty — sekcja po prostu się nie pokazuje. */
function usePart<T>(load: () => Promise<T>, key: string): Part<T> {
  const [result, setResult] = useState<{ key: string; part: Part<T> } | null>(null)
  useEffect(() => {
    let cancelled = false
    load()
      .then((data) => !cancelled && setResult({ key, part: { state: 'ok', data } }))
      .catch(() => !cancelled && setResult({ key, part: { state: 'unavailable' } }))
    return () => {
      cancelled = true
    }
    // `load` zmienia się z każdym renderem; ponowne wczytanie tylko przy zmianie `key`
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  return result && result.key === key ? result.part : { state: 'loading' }
}

/** Strona główna w trybie jaskółki: jedna spokojna lista „Dla Was”, bez kolorów akcentu i bez animacji. */
export default function JaskolkaHome() {
  const { mode, refresh } = useFamilyMode()
  const [error, setError] = useState<string | null>(null)
  const childId = mode.child_id ?? ''

  const family = usePart(() => api<FamilyView>('/api/families/me'), `family:${childId}`)
  const child = family.state === 'ok' ? family.data.children.find((c) => c.id === childId) : undefined
  const kind = child?.situation_kind ?? null

  const benefits = usePart(() => api<BenefitRow[]>('/api/benefits'), `benefits:${childId}`)
  const foundations = usePart(() => fetchFoundations(kind ?? 'smierc-dziecka'), `foundations:${kind}`)
  const calendar = usePart(() => api<CalendarEvent[]>('/api/calendar'), `calendar:${childId}`)

  const list = benefits.state === 'ok' ? benefits.data.filter((r) => r.benefit.tags.includes('loss_support') && r.match.status !== 'no') : []
  const otherDeadlines =
    calendar.state === 'ok'
      ? calendar.data.filter((e) => e.due_date && !e.done && e.child_id && e.child_id !== childId).slice(0, 5)
      : []

  const act = useCallback(
    async (call: () => Promise<unknown>) => {
      setError(null)
      try {
        await call()
        await refresh()
      } catch (e) {
        setError(e instanceof ApiError ? e.detail : 'Nie udało się zapisać zmiany. Spróbuj ponownie.')
      }
    },
    [refresh],
  )

  return (
    <div className="page page-narrow sit-home stack">
      <header>
        <h1>Dla Was</h1>
        <p className="sit-lead">
          Jesteśmy z Wami. Poniżej zebraliśmy to, co może się przydać. Nic nie jest pilne — możecie wracać tu w dowolnym
          momencie.
        </p>
        {kind && (
          <p>
            <Link to={`/jaskolka/${kind}`}>Pełna lista kroków i dokumentów</Link>
          </p>
        )}
      </header>

      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}

      <section aria-labelledby="sit-list-h" className="card stack">
        <h2 id="sit-list-h">Co może Wam przysługiwać</h2>
        {benefits.state === 'loading' && <p role="status">Wczytywanie…</p>}
        {benefits.state !== 'loading' && list.length === 0 && (
          <p className="muted">Na razie nie ma tu pozycji do pokazania. Pełna lista kroków jest na stronie powyżej.</p>
        )}
        <ul className="sit-items">
          {list.map(({ benefit }) => (
            <li key={benefit.id} className="sit-item">
              <h3>{benefit.name}</h3>
              <p>{benefit.description}</p>
              <p className="muted">{benefit.how_to_apply}</p>
              <p className="row">
                {benefit.form_codes.map((code) => (
                  <Link key={code} className="btn btn-secondary" to={`/wnioski/nowy?form=${encodeURIComponent(code)}`}>
                    Przygotuj wniosek ({code})
                  </Link>
                ))}
                <a href={benefit.source_url} target="_blank" rel="noopener noreferrer">
                  Źródło<span className="sit-sr"> (otwiera się w nowej karcie)</span>
                </a>
              </p>
              {benefit.form_codes.length > 0 && <p className="muted">Wniosek wypełnimy z danych z Waszego profilu.</p>}
            </li>
          ))}
        </ul>
      </section>

      {foundations.state === 'ok' && foundations.data.length > 0 && (
        <section aria-labelledby="sit-found-h" className="card stack">
          <h2 id="sit-found-h">Gdzie można znaleźć wsparcie</h2>
          <ul className="sit-items">
            {foundations.data.slice(0, 6).map((f: Foundation) => (
              <li key={f.id} className="sit-item">
                <a href={f.url} target="_blank" rel="noopener noreferrer">
                  {f.name}
                  <span className="sit-sr"> (otwiera się w nowej karcie)</span>
                </a>
                <p className="muted">{f.description}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {otherDeadlines.length > 0 && (
        <section aria-labelledby="sit-other-h" className="card stack sit-muted">
          <h2 id="sit-other-h">Terminy pozostałych dzieci</h2>
          <p className="muted">Pokazujemy je spokojnie, bez przypominania — wrócicie do nich, kiedy będziecie gotowi.</p>
          <ul className="sit-items">
            {otherDeadlines.map((e) => (
              <li key={e.id}>
                {e.title} <span className="muted">— do {formatDate(e.due_date as string)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <footer className="sit-footer row">
        {canUndo(mode) && (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => void act(() => api(`/api/families/me/children/${childId}/situation`, { method: 'DELETE' }))}
          >
            Cofnij zgłoszenie
          </button>
        )}
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => void act(() => api('/api/families/me/mode/exit', { method: 'POST' }))}
        >
          Wróć do zwykłego widoku
        </button>
      </footer>
    </div>
  )
}
