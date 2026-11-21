import { useCallback, useEffect, useId, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../lib/api'
import { useSession } from '../../lib/session'
import './notifications.css'

export interface AppNotification {
  id: string
  kind: string
  text: string
  link: string | null
  created_at: string
  read: boolean
}

const REFRESH_MS = 60_000

/** Dzwonek w nagłówku z licznikiem nieprzeczytanych powiadomień rodziny. */
export default function NotificationBell() {
  const { user, family } = useSession()
  const [items, setItems] = useState<AppNotification[]>([])
  const [open, setOpen] = useState(false)
  const panelId = useId()
  const enabled = user?.role === 'parent' && Boolean(family)

  const load = useCallback(() => {
    api<AppNotification[]>('/api/notifications')
      .then(setItems)
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!enabled) return
    load()
    const t = setInterval(load, REFRESH_MS)
    return () => clearInterval(t)
  }, [enabled, load])

  if (!enabled) return null
  const unread = items.filter((n) => !n.read).length

  async function markRead(n: AppNotification) {
    if (n.read) return
    setItems((prev) => prev.map((x) => (x.id === n.id ? { ...x, read: true } : x)))
    try {
      await api(`/api/notifications/${n.id}/read`, { method: 'POST' })
    } catch {
      load()
    }
  }

  return (
    <div className="bell">
      <button
        type="button"
        className="bell-button"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={unread ? `Powiadomienia: ${unread} nieprzeczytane` : 'Powiadomienia'}
        onClick={() => {
          setOpen((o) => !o)
          if (!open) load()
        }}
      >
        <svg aria-hidden="true" viewBox="0 0 24 24" width="22" height="22">
          <path
            fill="currentColor"
            d="M12 22a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 12 22Zm7-6V11a7 7 0 0 0-5.5-6.84V3a1.5 1.5 0 0 0-3 0v1.16A7 7 0 0 0 5 11v5l-2 2v1h18v-1Z"
          />
        </svg>
        {unread > 0 && <span className="bell-count">{unread > 9 ? '9+' : unread}</span>}
      </button>
      {open && (
        <div id={panelId} className="bell-panel" role="region" aria-label="Lista powiadomień">
          {items.length === 0 ? (
            <p className="muted">Brak powiadomień.</p>
          ) : (
            <ul>
              {items.slice(0, 10).map((n) => (
                <li key={n.id} className={n.read ? 'is-read' : undefined}>
                  <Link
                    to={n.link ?? '/'}
                    onClick={() => {
                      void markRead(n)
                      setOpen(false)
                    }}
                  >
                    {n.text}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
