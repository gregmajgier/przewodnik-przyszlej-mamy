import { lazy, Suspense, useLayoutEffect } from 'react'

// Osobny chunk: reszta aplikacji nie ładuje kodu /jaskolka. (`lazy` z RouteObject działa tylko
// w data routerze, a App używa <BrowserRouter>, więc używamy React.lazy.)
const JaskolkaPage = lazy(() => import('./JaskolkaPage'))

export default function JaskolkaLazy() {
  // Motyw mono od pierwszej klatki: także krótkie „Wczytywanie…” ma być szare, bez kolorów aplikacji.
  useLayoutEffect(() => {
    const root = document.documentElement
    const previous = root.dataset.theme
    root.dataset.theme = 'mono'
    return () => {
      if (previous === undefined) delete root.dataset.theme
      else root.dataset.theme = previous
    }
  }, [])
  return (
    <Suspense fallback={<p role="status" style={{ margin: 0, padding: "2rem clamp(1rem, 4vw, 3rem)", color: "var(--muted)" }}>Wczytywanie…</p>}>
      <JaskolkaPage />
    </Suspense>
  )
}
