import { useEffect, useRef, useState } from 'react'
import { Link, Navigate, Outlet, useLocation } from 'react-router-dom'
import { Wordmark } from '../../brand/Splash'
import { api } from '../../lib/api'
import { useSession } from '../../lib/session'
import { Icon } from '../../ui/Icon'
import { Avatar } from '../../ui/controls'
import '../../brand/brand.css'
import '../../ui/ui.css'
import '../../components/shell.css'
import './official.css'
import { LEVEL_LABEL } from './types'
import type { Unit } from './types'

function AccountMenu({ name, unit, onLogout }: { name: string; unit: Unit | null; onLogout: () => void }) {
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
        <Avatar name={name} tone="lilac" size={38} icon="shield" />
      </button>
      {open && (
        <div className="user-menu-panel" role="menu">
          <div className="user-menu-head">
            <Avatar name={name} tone="lilac" size={44} icon="shield" />
            <div>
              <strong>{name}</strong>
              <span className="muted small">{unit ? `${LEVEL_LABEL[unit.level]} · ${unit.name}` : 'Konto urzędnika'}</span>
            </div>
          </div>
          <Link to="/urzednik" role="menuitem" className="user-menu-item">
            <Icon name="gift" size={20} />
            Świadczenia
          </Link>
          <Link to="/urzednik/swiadczenia/nowe" role="menuitem" className="user-menu-item">
            <Icon name="plus" size={20} />
            Nowe świadczenie
          </Link>
          <button type="button" role="menuitem" className="user-menu-item" onClick={onLogout}>
            <Icon name="logout" size={20} />
            Wyloguj
          </button>
        </div>
      )}
    </div>
  )
}

/** Osobna powłoka panelu urzędnika (poza AppShell rodzica). */
export default function OfficialLayout() {
  const { user, loading, logout } = useSession()
  const [unit, setUnit] = useState<Unit | null>(null)
  const isOfficial = user?.role === 'official'

  useEffect(() => {
    if (!isOfficial) return
    let cancelled = false
    api<{ unit: Unit }>('/api/official/me')
      .then((r) => !cancelled && setUnit(r.unit))
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [isOfficial])

  if (loading) return <p role="status" className="page">Ładowanie…</p>
  if (!isOfficial) return <Navigate to="/urzednik/logowanie" replace />

  return (
    <div className="shell off-shell">
      <header className="shell-header">
        <div className="shell-header-inner">
          <Link to="/urzednik" className="shell-brand off-brand" aria-label="mRodzina — panel samorządu">
            <Wordmark />
            <span className="off-brand-tag">Samorząd</span>
          </Link>
          <div className="shell-actions">
            {unit && (
              <span className="off-unit-chip">
                <Icon name="pin" size={16} />
                {unit.name}
              </span>
            )}
            <AccountMenu name={user.name} unit={unit} onLogout={logout} />
          </div>
        </div>
      </header>
      <main className="shell-main">
        <Outlet context={unit} />
      </main>
    </div>
  )
}
