import { useContext, useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { api } from '../../lib/api'
import { SessionContext } from '../../lib/session'
import { Icon } from '../../ui/Icon'
import { clearLastChat, getLastChat, onLastChatChange } from './lastChat'
import './chat.css'

interface SessionItem {
  id: string
  preview: string
}

/** Pływający przycisk „Zapytaj mRodzinę” — z każdego ekranu otwiera czat. Kontekst ekranu trafia do czatu.
 * Nad nim karta „Ostatnia rozmowa”, która wraca do przerwanej rozmowy. */
export function AskFab() {
  const { pathname } = useLocation()
  // bez wyjątku poza providerem (np. w testach): bez użytkownika po prostu nic nie zapamiętujemy
  const userId = useContext(SessionContext)?.user?.id
  const [lastId, setLastId] = useState(() => getLastChat(userId))
  // podgląd ostatniej rozmowy z API; pokazujemy go tylko, gdy dotyczy aktualnego `lastId`
  const [last, setLast] = useState<SessionItem | null>(null)

  useEffect(() => onLastChatChange(() => setLastId(getLastChat(userId))), [userId])

  useEffect(() => {
    if (!lastId) return
    let cancelled = false
    api<SessionItem[]>('/api/chat/sessions')
      .then((list) => {
        if (cancelled) return
        const found = list.find((s) => s.id === lastId)
        if (found) setLast(found)
        else clearLastChat(userId) // rozmowa już nie istnieje
      })
      .catch(() => {
        // bez podglądu karta się po prostu nie pokaże
      })
    return () => {
      cancelled = true
    }
  }, [lastId, userId])

  const showLast = lastId !== null && last?.id === lastId

  return (
    <>
      {showLast && (
        <div className="ask-last">
          <Link to="/czat" state={{ from: pathname, resume: lastId }} className="ask-last-open">
            <Icon name="history" size={18} />
            <span className="ask-last-text">
              <span className="ask-last-label">Ostatnia rozmowa</span>
              <span className="ask-last-preview">{last.preview || 'Rozmowa z asystentem'}</span>
            </span>
          </Link>
          <button type="button" className="ask-last-close" aria-label="Ukryj ostatnią rozmowę" onClick={() => clearLastChat(userId)}>
            <Icon name="close" size={16} />
          </button>
        </div>
      )}
      <Link to="/czat" state={{ from: pathname }} className="ask-fab" aria-label="Zapytaj mRodzinę">
        <span className="ask-fab-icon">
          <Icon name="sparkle" size={24} />
        </span>
        <span className="ask-fab-label">Zapytaj</span>
      </Link>
    </>
  )
}
