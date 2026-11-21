import { lazy, Suspense } from 'react'
import type { RouteObject } from 'react-router-dom'

// Osobny chunk: reszta aplikacji nie ładuje kodu /jaskolka. (`lazy` z RouteObject działa tylko
// w data routerze, a App używa <BrowserRouter>, więc używamy React.lazy.)
const JaskolkaPage = lazy(() => import('./JaskolkaPage'))

const element = (
  <Suspense fallback={<p role="status">Wczytywanie…</p>}>
    <JaskolkaPage />
  </Suspense>
)

// `handle.public`: trasa poza AppShell, bez wymaganej sesji.
const routes: RouteObject[] = [
  { path: '/jaskolka', element, handle: { public: true } },
  { path: '/jaskolka/:situationId', element, handle: { public: true } },
]

export default routes
