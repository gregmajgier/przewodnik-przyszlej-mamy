import type { RouteObject } from 'react-router-dom'
import JaskolkaLazy from './JaskolkaLazy'

// `handle.public`: trasa poza AppShell, bez wymaganej sesji.
const routes: RouteObject[] = [
  { path: '/jaskolka', element: <JaskolkaLazy />, handle: { public: true } },
  { path: '/jaskolka/:situationId', element: <JaskolkaLazy />, handle: { public: true } },
]

export default routes
