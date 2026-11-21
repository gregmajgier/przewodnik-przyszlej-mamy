import { BrowserRouter, Navigate, useRoutes } from 'react-router-dom'
import type { RouteObject } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { featureRoutes } from './features/registry'
import { SessionProvider, useSession } from './lib/session'

function isPublic(route: RouteObject): boolean {
  return (route.handle as { public?: boolean } | undefined)?.public === true
}

/** Strona startowa, dopóki żadna funkcja nie dostarczy własnej trasy "/" (dashboard — plan 03). */
function HomeRedirect() {
  const { family } = useSession()
  return <Navigate to={family ? '/rodzina' : '/start'} replace />
}

function NotFound() {
  return (
    <div className="card">
      <h1>Nie znaleziono strony</h1>
      <p className="muted">Sprawdź adres albo wróć do strony głównej.</p>
    </div>
  )
}

function buildRoutes(routes: RouteObject[] = featureRoutes): RouteObject[] {
  const publicRoutes = routes.filter(isPublic)
  const protectedRoutes = routes.filter((r) => !isPublic(r))
  const hasHome = protectedRoutes.some((r) => r.path === '/' || r.index === true)
  return [
    ...publicRoutes,
    {
      element: <AppShell />,
      children: [
        ...(hasHome ? [] : [{ path: '/', element: <HomeRedirect /> }]),
        ...protectedRoutes,
        { path: '*', element: <NotFound /> },
      ],
    },
  ]
}

function AppRoutes() {
  return useRoutes(buildRoutes())
}

export default function App() {
  return (
    <SessionProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </SessionProvider>
  )
}
