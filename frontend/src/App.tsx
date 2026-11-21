import { useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Outlet, useLocation, useRoutes } from 'react-router-dom'
import type { RouteObject } from 'react-router-dom'
import { Splash } from './brand/Splash'
import { AppShell } from './components/AppShell'
import { featureRoutes } from './features/registry'
import { SessionProvider, useSession } from './lib/session'

type Handle = { public?: boolean; flow?: boolean } | undefined

const isPublic = (r: RouteObject) => (r.handle as Handle)?.public === true
const isFlow = (r: RouteObject) => (r.handle as Handle)?.flow === true

/** Ekrany „przepływu” (onboarding, analiza, czat): pełny ekran bez nagłówka panelu, ale z wymaganą sesją. */
function FlowGuard() {
  const { user, loading } = useSession()
  const location = useLocation()
  if (loading) return <Splash />
  if (!user) return <Navigate to="/logowanie" replace state={{ from: location.pathname }} />
  return <Outlet />
}

function NotFound() {
  return (
    <div className="page page-narrow">
      <div className="card empty">
        <h1>Nie znaleziono strony</h1>
        <p className="muted">Sprawdź adres albo wróć do strony głównej.</p>
      </div>
    </div>
  )
}

function buildRoutes(routes: RouteObject[] = featureRoutes): RouteObject[] {
  const publicRoutes = routes.filter(isPublic)
  const flowRoutes = routes.filter((r) => !isPublic(r) && isFlow(r))
  const shellRoutes = routes.filter((r) => !isPublic(r) && !isFlow(r))
  return [
    ...publicRoutes,
    { element: <FlowGuard />, children: flowRoutes },
    {
      element: <AppShell />,
      children: [...shellRoutes, { path: '*', element: <NotFound /> }],
    },
  ]
}

function AppRoutes() {
  return useRoutes(buildRoutes())
}

const SPLASH_MS = 1700

/** Ekran ładowania przy wejściu do aplikacji: raz na kartę, żeby animacja logo miała czas się narysować. */
function useBootSplash(): boolean {
  const [show, setShow] = useState(() => {
    if (import.meta.env.MODE === 'test') return false
    try {
      return sessionStorage.getItem('mr-splash') !== '1'
    } catch {
      return true
    }
  })
  useEffect(() => {
    if (!show) return
    const t = window.setTimeout(() => {
      setShow(false)
      try {
        sessionStorage.setItem('mr-splash', '1')
      } catch {
        // brak sessionStorage — splash pokaże się przy kolejnym wejściu
      }
    }, SPLASH_MS)
    return () => window.clearTimeout(t)
  }, [show])
  return show
}

function Boot() {
  const splash = useBootSplash()
  const { loading } = useSession()
  if (splash || loading) return <Splash />
  return <AppRoutes />
}

export default function App() {
  return (
    <SessionProvider>
      <BrowserRouter>
        <Boot />
      </BrowserRouter>
    </SessionProvider>
  )
}
