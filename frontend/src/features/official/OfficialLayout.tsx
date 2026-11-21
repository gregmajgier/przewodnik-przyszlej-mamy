import { useEffect, useState } from 'react'
import { NavLink, Navigate, Outlet } from 'react-router-dom'
import { Logo } from '../../components/Logo'
import { api } from '../../lib/api'
import { useSession } from '../../lib/session'
import { navItems } from '../registry'
import './official.css'
import type { Unit } from './types'

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

  if (loading) return <p role="status" className="official-main">Ładowanie…</p>
  if (!isOfficial) return <Navigate to="/urzednik/logowanie" replace />

  const items = navItems.filter((n) => n.area === 'official')

  return (
    <>
      <header className="official-header">
        <NavLink to="/urzednik" end className="row" aria-label="mRodzina, panel jednostki">
          <Logo className="logo-mark" animate={false} />
          <span className="wordmark">Rodzina</span>
        </NavLink>
        <nav className="row" aria-label="Panel jednostki">
          {items.map((n) => (
            <NavLink key={n.path} to={n.path} end>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="row" style={{ marginLeft: 'auto' }}>
          <span>
            {user.name}
            {unit && <> · {unit.name}</>}
          </span>
          <button className="btn btn-secondary" type="button" onClick={logout}>
            Wyloguj
          </button>
        </div>
      </header>
      <main className="official-main">
        <Outlet />
      </main>
    </>
  )
}
