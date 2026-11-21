import { useCallback, useEffect, useMemo, useState } from 'react'
import { NavLink, Navigate, Outlet, useLocation } from 'react-router-dom'
import { headerSlots, navItems } from '../features/registry'
import JaskolkaHome from '../features/situations/JaskolkaHome'
import { FamilyModeContext, useFamilyModeState } from '../features/situations/useFamilyMode'
import { useSession } from '../lib/session'
import { Logo } from './Logo'

// Powłoka aplikacji: nagłówek + nawigacja z plików nav.ts funkcji + <Outlet/>. Wymaga sesji.
export function AppShell() {
  const { user, family, loading, logout, refresh: refreshSession } = useSession()
  const location = useLocation()
  // Tryb jaskółki (plan 10): motyw monochromatyczny i jedna lista „Dla Was” zamiast dashboardu.
  const modeState = useFamilyModeState(user?.role === 'parent' && family !== null)
  // „Więcej” jest otwarte tylko na stronie, na której je otwarto (po przejściu gdzie indziej zamyka się samo)
  const [moreAt, setMoreAt] = useState<string | null>(null)
  // po zgłoszeniu/cofnięciu/wyjściu odświeżamy też sesję: lista dzieci (np. w kreatorze wniosków) musi być aktualna
  const refreshMode = modeState.refresh
  const refreshAll = useCallback(async () => {
    await refreshMode()
    await refreshSession()
  }, [refreshMode, refreshSession])
  const familyMode = useMemo(() => ({ mode: modeState.mode, refresh: refreshAll }), [modeState.mode, refreshAll])
  const inJaskolkaMode = familyMode.mode.mode === 'jaskolka'

  useEffect(() => {
    if (!inJaskolkaMode) return
    const root = document.documentElement
    const previous = root.dataset.theme
    root.dataset.theme = 'mono'
    return () => {
      if (previous === undefined) delete root.dataset.theme
      else root.dataset.theme = previous
    }
  }, [inJaskolkaMode])

  if (loading) {
    return (
      <p role="status" className="shell-main">
        Ładowanie…
      </p>
    )
  }
  if (!user) {
    return <Navigate to="/logowanie" replace state={{ from: location.pathname }} />
  }

  const area = user.role === 'official' ? 'official' : 'parent'
  const moreOpen = moreAt === location.pathname
  const items = navItems.filter((n) => n.area === area)
  const hasPrimary = items.some((n) => n.primary)
  const primary = hasPrimary ? items.filter((n) => n.primary) : items
  const secondary = hasPrimary ? items.filter((n) => !n.primary) : []
  const link = (n: (typeof items)[number]) => (
    <NavLink key={n.path} to={n.path} end={n.path === '/'}>
      {n.label}
    </NavLink>
  )

  return (
    <>
      <header className="shell-header">
        <NavLink to="/" className="shell-brand" aria-label="mRodzina, strona główna">
          <Logo className="logo-mark" animate={false} />
          <span className="wordmark">Rodzina</span>
        </NavLink>
        <nav className="shell-nav" aria-label="Główna">
          <div className="nav-bar">
            {primary.map(link)}
            {secondary.length > 0 && (
              <button
                type="button"
                className="nav-more"
                aria-expanded={moreOpen}
                aria-controls="nav-sheet"
                onClick={() => setMoreAt(moreOpen ? null : location.pathname)}
              >
                Więcej
              </button>
            )}
          </div>
          <div id="nav-sheet" className={`nav-sheet${moreOpen ? ' is-open' : ''}`}>
            {secondary.map(link)}
          </div>
        </nav>
        <div className="shell-user">
          {area === 'parent' && headerSlots.map((h, i) => <h.Component key={i} />)}
          <span className="shell-user-name">{user.name}</span>
          <button type="button" className="btn btn-secondary" onClick={logout}>
            Wyloguj
          </button>
        </div>
      </header>
      <FamilyModeContext.Provider value={familyMode}>
        <main className="shell-main">{inJaskolkaMode && location.pathname === '/' ? <JaskolkaHome /> : <Outlet />}</main>
      </FamilyModeContext.Provider>
    </>
  )
}
