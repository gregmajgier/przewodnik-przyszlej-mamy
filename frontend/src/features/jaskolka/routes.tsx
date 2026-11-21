import type { RouteObject } from 'react-router-dom'
import JaskolkaLazy from './JaskolkaLazy'

const element = <JaskolkaLazy />

// `handle.public`: trasa poza AppShell, bez wymaganej sesji.
const routes: RouteObject[] = [
  { path: '/jaskolka', element, handle: { public: true } },
  { path: '/jaskolka/:situationId', element, handle: { public: true } },
]

export default routes
