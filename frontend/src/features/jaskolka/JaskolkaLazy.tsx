import { lazy, Suspense } from 'react'

// Osobny chunk: reszta aplikacji nie ładuje kodu /jaskolka. (`lazy` z RouteObject działa tylko
// w data routerze, a App używa <BrowserRouter>, więc używamy React.lazy.)
const JaskolkaPage = lazy(() => import('./JaskolkaPage'))

export default function JaskolkaLazy() {
  return (
    <Suspense fallback={<p role="status">Wczytywanie…</p>}>
      <JaskolkaPage />
    </Suspense>
  )
}
