import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Logo } from '../../components/Logo'
import { Checklist } from './Checklist'
import { Foundations } from './Foundations'
import { SituationPicker } from './SituationPicker'
import { fetchSituation, fetchSituations } from './jaskolkaApi'
import type { SituationDetail, SituationSummary } from './jaskolkaApi'
import './jaskolka.css'

/** Motyw monochromatyczny na czas wizyty na /jaskolka; po wyjściu wraca poprzedni. */
function useMonoTheme() {
  useEffect(() => {
    const root = document.documentElement
    const previous = root.dataset.theme
    root.dataset.theme = 'mono'
    return () => {
      if (previous === undefined) delete root.dataset.theme
      else root.dataset.theme = previous
    }
  }, [])
}

type Load<T> = { state: 'loading' } | { state: 'error'; message: string } | { state: 'ok'; data: T }

function useLoad<T>(load: () => Promise<T>, key: string): Load<T> {
  const [result, setResult] = useState<{ key: string; value: Load<T> } | null>(null)
  useEffect(() => {
    let cancelled = false
    load()
      .then((data) => {
        if (!cancelled) setResult({ key, value: { state: 'ok', data } })
      })
      .catch((e: unknown) => {
        if (!cancelled)
          setResult({
            key,
            value: { state: 'error', message: e instanceof Error ? e.message : 'Nie udało się wczytać strony.' },
          })
      })
    return () => {
      cancelled = true
    }
    // `load` zmienia się razem z `key`
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  return result && result.key === key ? result.value : { state: 'loading' }
}

function Header({ inSituation }: { inSituation: boolean }) {
  return (
    <header className="jk-header">
      <Link to="/jaskolka" className="jk-brand" aria-label="mRodzina: wsparcie, strona początkowa">
        <Logo className="jk-logo" animate={false} />
        <span className="wordmark">Rodzina</span>
      </Link>
      <nav aria-label="Nawigacja" className="jk-nav">
        {inSituation && (
          <Link to="/jaskolka" className="jk-back">
            ← Wróć do wyboru sytuacji
          </Link>
        )}
        {/* pełne przeładowanie, żeby aplikacja odtworzyła sesję */}
        <a href="/" className="jk-back">
          Wróć do mRodziny
        </a>
      </nav>
    </header>
  )
}

function Helpline() {
  // Numery pomocy widać zawsze, bez klikania: osoba w kryzysie nie powinna ich szukać.
  return (
    <footer className="jk-help">
      <p className="jk-help-line">
        Telefon wsparcia emocjonalnego: <a href="tel:116123">116 123</a>, bezpłatnie i całą dobę.{' '}
        Jeśli ktoś jest w niebezpieczeństwie: <a href="tel:112">112</a>.{' '}
        <a
          href="https://www.gov.pl/web/zdrowie/gdzie-uzyskac-pomoc-psychologiczna-i-psychiatryczna"
          target="_blank"
          rel="noopener noreferrer"
        >
          Więcej miejsc pomocy<span className="jk-sr"> (otwiera się w nowej karcie)</span>
        </a>
      </p>
    </footer>
  )
}

function Picker() {
  const list = useLoad<SituationSummary[]>(fetchSituations, 'list')
  if (list.state === 'loading') return <p role="status">Wczytywanie…</p>
  if (list.state === 'error') return <p role="alert" className="jk-note">{list.message}</p>
  return <SituationPicker situations={list.data} />
}

function Situation({ id }: { id: string }) {
  const detail = useLoad<SituationDetail>(() => fetchSituation(id), `s:${id}`)
  if (detail.state === 'loading') return <p role="status">Wczytywanie…</p>
  if (detail.state === 'error') {
    return (
      <section>
        <p role="alert" className="jk-note">
          {detail.message}
        </p>
        <p>
          <Link to="/jaskolka" className="jk-btn">
            Wybierz sytuację z listy
          </Link>
        </p>
      </section>
    )
  }
  return (
    <>
      <Checklist key={detail.data.id} situation={detail.data} />
      <Foundations key={id} situationId={id} />
    </>
  )
}

export function Component() {
  useMonoTheme()
  const { situationId } = useParams()
  return (
    <div className="jk">
      <a className="jk-skip" href="#jk-main">
        Przejdź do treści
      </a>
      <Header inSituation={Boolean(situationId)} />
      <main id="jk-main" className="jk-main">
        {situationId ? <Situation id={situationId} /> : <Picker />}
      </main>
      <Helpline />
    </div>
  )
}

export default Component
