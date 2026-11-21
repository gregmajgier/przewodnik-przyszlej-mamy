import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Logo } from '../../components/Logo'
import { api } from '../../lib/api'
import { timeAgo } from '../../lib/format'
import { Icon } from '../../ui/Icon'
import type { IconName } from '../../ui/Icon'
import { Sheet } from '../../ui/Sheet'
import { Message } from './Message'
import { MAX_MESSAGE_CHARS, useChatStream } from './useChatStream'
import '../../ui/ui.css'
import './chat.css'

const SUGGESTIONS: { icon: IconName; title: string; q: string }[] = [
  { icon: 'briefcase', title: 'Urlop macierzyński', q: 'Jak działa urlop macierzyński?' },
  { icon: 'blocks', title: 'Przedszkole', q: 'Jak zapisać dziecko do przedszkola?' },
  { icon: 'coins', title: 'Ile możemy dostać', q: 'Ile pieniędzy możemy dostać w tym roku jako rodzina?' },
  { icon: 'calendar', title: 'Po porodzie', q: 'Co muszę załatwić w pierwszym miesiącu po porodzie?' },
]

interface RouteState {
  q?: unknown
  context?: unknown
  autoSend?: unknown
  from?: unknown
}

interface SessionItem {
  id: string
  updated_at: string
  preview: string
}

export default function ChatPage() {
  const { messages, sending, banner, error, send, reset, stop, open } = useChatStream()
  const location = useLocation()
  const navigate = useNavigate()
  const state = (location.state ?? {}) as RouteState
  const initialQ = typeof state.q === 'string' ? state.q.slice(0, MAX_MESSAGE_CHARS) : ''
  const context = typeof state.context === 'string' ? state.context : ''
  // Pytanie z kafelka trafia do pola (router state); wysyłamy je od razu tylko po kliknięciu w aplikacji
  // (`autoSend`), nigdy z parametrów adresu URL — link z zewnątrz nie może zużyć budżetu AI.
  const auto = state.autoSend === true && initialQ !== ''
  const [draft, setDraft] = useState(auto ? '' : initialQ)
  const [history, setHistory] = useState<SessionItem[] | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const scroller = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const autoSent = useRef(false)

  useEffect(() => {
    if (!auto || autoSent.current) return
    const t = window.setTimeout(() => {
      autoSent.current = true
      void send(context ? `${initialQ}\n\n(Chodzi o: ${context}.)` : initialQ)
      navigate(location.pathname, { replace: true, state: { from: state.from } })
    }, 40)
    return () => window.clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const el = scroller.current
    if (el && typeof el.scrollTo === 'function') el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [messages])

  useLayoutEffect(() => {
    const el = input.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`
  }, [draft])

  function submit(e?: FormEvent) {
    e?.preventDefault()
    const text = draft.trim()
    if (!text || sending) return
    setDraft('')
    void send(text)
  }

  async function openHistory() {
    setHistoryOpen(true)
    try {
      setHistory(await api<SessionItem[]>('/api/chat/sessions'))
    } catch {
      setHistory([])
    }
  }

  function back() {
    const from = typeof state.from === 'string' ? state.from : '/'
    navigate(from)
  }

  const empty = messages.length === 0

  return (
    <div className="chat-screen">
      <header className="chat-top">
        <button type="button" className="icon-btn" aria-label="Wróć" onClick={back}>
          <Icon name="arrowLeft" size={22} />
        </button>
        <div className="chat-top-title">
          <span className="chat-top-logo" aria-hidden="true">
            <Logo className="msg-logo" color="#fff" animate={false} />
          </span>
          <h1>Zapytaj mRodzinę</h1>
        </div>
        <div className="chat-top-actions">
          <button type="button" className="icon-btn" aria-label="Historia rozmów" onClick={() => void openHistory()}>
            <Icon name="history" size={22} />
          </button>
          <button type="button" className="icon-btn" aria-label="Nowa rozmowa" onClick={reset} disabled={empty}>
            <Icon name="edit" size={21} />
          </button>
        </div>
      </header>

      <div className="chat-scroll" ref={scroller}>
        <div className="chat-column">
          {empty ? (
            <div className="chat-empty">
              <div className="chat-empty-logo">
                <Logo className="chat-hero-logo" color="#fff" duration={1300} />
              </div>
              <h2>W czym mogę Ci pomóc?</h2>
              <p className="muted">Pytaj o urlopy, zasiłki, żłobek, przedszkole i szkołę. Odpowiadam na podstawie przepisów i Waszych danych — zawsze ze źródłem.</p>
              <div className="chat-suggestions">
                {SUGGESTIONS.map((s, i) => (
                  <button
                    key={s.q}
                    type="button"
                    className="chat-suggestion rise"
                    style={{ ['--i' as string]: i + 1 }}
                    onClick={() => void send(s.q)}
                    disabled={sending}
                  >
                    <Icon name={s.icon} size={20} />
                    <span className="chat-suggestion-title">{s.title}</span>
                    <span className="chat-suggestion-q">{s.q}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="chat-log" role="log" aria-live="polite" aria-label="Rozmowa">
              {messages.map((m, i) => (
                <Message key={m.id} message={m} streaming={sending && i === messages.length - 1} />
              ))}
            </div>
          )}
          {banner && (
            <p className="notice chat-banner" role="status">
              {banner}
            </p>
          )}
          {error && (
            <p className="alert" role="alert">
              <Icon name="alert" size={20} />
              {error}
            </p>
          )}
        </div>
      </div>

      <div className="chat-dock">
        <form className="composer" onSubmit={submit}>
          <label htmlFor="chat-input" className="sr-only">
            Twoje pytanie
          </label>
          <textarea
            id="chat-input"
            ref={input}
            rows={1}
            value={draft}
            maxLength={MAX_MESSAGE_CHARS}
            placeholder="Zapytaj o cokolwiek…"
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) submit(e)
            }}
          />
          {sending ? (
            <button type="button" className="composer-send is-stop" onClick={stop} aria-label="Zatrzymaj odpowiedź">
              <Icon name="stop" size={18} stroke={2.4} />
            </button>
          ) : (
            <button type="submit" className="composer-send" disabled={draft.trim() === ''} aria-label="Wyślij">
              <Icon name="arrowUp" size={20} stroke={2.4} />
            </button>
          )}
        </form>
        <p className="chat-disclaimer">Pomoc informacyjna, nie porada prawna. Ważne decyzje potwierdź w ZUS lub urzędzie.</p>
      </div>

      <Sheet open={historyOpen} onClose={() => setHistoryOpen(false)} title="Historia rozmów">
        {!history && <div className="skeleton" style={{ height: '3.5rem' }} role="status" aria-label="Wczytuję historię" />}
        {history?.length === 0 && <p className="muted">Nie masz jeszcze zapisanych rozmów.</p>}
        <ul className="list">
          {history?.map((h) => (
            <li key={h.id}>
              <button
                type="button"
                className="list-row"
                onClick={() => {
                  setHistoryOpen(false)
                  void open(h.id)
                }}
              >
                <span className="icon-tile">
                  <Icon name="chat" size={20} />
                </span>
                <span className="list-row-main">
                  <span className="list-row-title">{h.preview || 'Rozmowa'}</span>
                  <span className="list-row-sub">{timeAgo(h.updated_at)}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      </Sheet>
    </div>
  )
}
