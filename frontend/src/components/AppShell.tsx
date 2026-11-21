import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, Navigate, NavLink, Outlet, useLocation } from 'react-router-dom'
import { Splash, Wordmark } from '../brand/Splash'
import { AskFab } from '../features/chat/AskFab'
import { headerSlots } from '../features/registry'
import JaskolkaHome from '../features/situations/JaskolkaHome'
import { FamilyModeContext, useFamilyModeState } from '../features/situations/useFamilyMode'
import { useSession } from '../lib/session'
import { isOnboarded } from '../lib/onboarding'
import { Icon } from '../ui/Icon'
import type { IconName } from '../ui/Icon'
import { Avatar } from '../ui/controls'
import '../brand/brand.css'
import '../ui/ui.css'
import './shell.css'

const MENU: { to: string; label: string; icon: IconName }[] = [
  { to: '/rodzina', label: 'Rodzina', icon: 'family' },
  { to: '/dane', label: 'Moje dane', icon: 'user' },
  { to: '/umowy', label: 'Umowy o pracę', icon: 'briefcase' },
  { to: '/kalendarz', label: 'Kalendarz', icon: 'calendar' },
]

function UserMenu({ name, onLogout }: { name: string; onLogout: () => void }) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const location = useLocation()

  useEffect(() => setOpen(false), [location.pathname])
  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => root.current && !root.current.contains(e.target as Node) && setOpen(false)
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div className="user-menu" ref={root}>
      <button
        type="button"
        className="user-menu-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Konto: ${name}`}
        onClick={() => setOpen((o) => !o)}
      >
        <Avatar name={name} tone="peach" size={38} />
      </button>
      {open && (
        <div className="user-menu-panel" role="menu">
          <div className="user-menu-head">
            <Avatar name={name} tone="peach" size={44} />
            <div>
              <strong>{name}</strong>
              <span className="muted small">Zalogowano przez mObywatel</span>
            </div>
          </div>
          {MENU.map((m) => (
            <NavLink key={m.to} to={m.to} role="menuitem" className="user-menu-item">
              <Icon name={m.icon} size={20} />
              {m.label}
            </NavLink>
          ))}
          <button type="button" role="menuitem" className="user-menu-item" onClick={onLogout}>
            <Icon name="logout" size={20} />
            Wyloguj
          </button>
        </div>
      )}
    </div>
  )
}

// Powłoka aplikacji: lekki nagłówek (wordmark, powiadomienia, konto) bez nawigacji — do ekranów prowadzą kafelki
// panelu. Na każdym ekranie pływający przycisk „Zapytaj”. Wymaga sesji.
export function AppShell() {
  const { user, family, loading, logout, refresh: refreshSession } = useSession()
  const location = useLocation()
  const modeState = useFamilyModeState(user?.role === 'parent' && family !== null)
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

  useEffect(() => {
    window.scrollTo?.({ top: 0 })
  }, [location.pathname])

  if (loading) return <Splash />
  if (!user) return <Navigate to="/logowanie" replace state={{ from: location.pathname }} />
  if (user.role === 'official') return <Navigate to="/urzednik" replace />
  if (!family || !isOnboarded(user.id)) return <Navigate to="/start" replace />

  return (
    <div className="shell">
      <header className="shell-header">
        <div className="shell-header-inner">
          <Link to="/" className="shell-brand" aria-label="mRodzina — panel główny">
            <Wordmark />
          </Link>
          <div className="shell-actions">
            {headerSlots.map((h, i) => (
              <h.Component key={i} />
            ))}
            <UserMenu name={user.name} onLogout={logout} />
          </div>
        </div>
      </header>
      <FamilyModeContext.Provider value={familyMode}>
        <main className="shell-main">{inJaskolkaMode && location.pathname === '/' ? <JaskolkaHome /> : <Outlet />}</main>
      </FamilyModeContext.Provider>
      {family && <AskFab />}
    </div>
  )
}
