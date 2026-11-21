import type { RouteObject } from 'react-router-dom'
import LoginPage from './LoginPage'

// `handle.public` — trasa poza powłoką (bez wymaganej sesji).
const routes: RouteObject[] = [{ path: '/logowanie', element: <LoginPage />, handle: { public: true } }]

export default routes
