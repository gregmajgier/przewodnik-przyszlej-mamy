import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { useLocation } from 'react-router-dom'
import { Message } from './Message'
import { MAX_MESSAGE_CHARS, useChatStream } from './useChatStream'
import './chat.css'

const EXAMPLE_QUESTIONS = ['Jak działa urlop macierzyński?', 'Jak zapisać dziecko do przedszkola?']

export default function ChatPage() {
  const { messages, sending, banner, error, send, reset } = useChatStream()
  // Pytanie z kafelka dashboardu trafia tylko do pola (router state) — nigdy nie wysyłamy niczego
  // automatycznie, a parametry adresu URL są ignorowane (link z zewnątrz nie może zużyć budżetu AI).
  const location = useLocation()
  const [draft, setDraft] = useState(() => {
    const q = (location.state as { q?: unknown } | null)?.q
    return typeof q === 'string' ? q.slice(0, MAX_MESSAGE_CHARS) : ''
  })
  const logRef = useRef<HTMLDivElement>(null)

  // Odpowiedzi przewija cała strona (bez własnego okienka z paskiem): po nowej wiadomości pokazujemy jej koniec.
  useEffect(() => {
    if (messages.length === 0) return
    const last = logRef.current?.lastElementChild
    if (last && typeof last.scrollIntoView === 'function') last.scrollIntoView({ block: 'nearest' })
  }, [messages])

  function submit(e: FormEvent) {
    e.preventDefault()
    const text = draft.trim()
    if (!text || sending) return
    setDraft('')
    void send(text)
  }

  return (
    <div className="chat stack">
      <header className="chat-head">
        <div>
          <h1>Zapytaj mRodzinę</h1>
          <p className="muted">
            Odpowiadam na podstawie przepisów, danych Twojej rodziny i oficjalnych stron. Zawsze podaję źródło.
          </p>
        </div>
        <button type="button" className="btn btn-secondary" onClick={reset}>
          Nowa rozmowa
        </button>
      </header>

      {banner && (
        <p className="notice chat-banner" role="status">
          {banner}
        </p>
      )}

      <div className="chat-log" ref={logRef} role="log" aria-live="polite" aria-label="Rozmowa">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <p>Zapytaj o urlop, zasiłki, żłobek, przedszkole albo szkołę. Na przykład:</p>
            <div className="row">
              {EXAMPLE_QUESTIONS.map((q) => (
                <button key={q} type="button" className="btn btn-secondary" onClick={() => void send(q)} disabled={sending}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m, i) => <Message key={m.id} message={m} streaming={sending && i === messages.length - 1} />)
        )}
      </div>

      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}

      <div className="chat-composer">
        <form className="chat-form" onSubmit={submit}>
          <label className="field" htmlFor="chat-input">
            <span>Twoje pytanie</span>
            <textarea
              id="chat-input"
              rows={2}
              value={draft}
              maxLength={MAX_MESSAGE_CHARS}
              placeholder="Np. Co mi przysługuje, gdy wrócę do pracy?"
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) submit(e)
              }}
            />
          </label>
          <button type="submit" className="btn" disabled={sending || draft.trim() === ''}>
            {sending ? 'Odpowiadam…' : 'Wyślij'}
          </button>
        </form>
      </div>
      <p className="muted chat-disclaimer">
        To pomoc informacyjna, nie porada prawna. Przy wątpliwościach zapytaj w urzędzie gminy, ZUS albo powiatowym
        urzędzie pracy. Czat nie składa wniosków, tylko wskaże Ci, jak to zrobić w aplikacji.
      </p>
    </div>
  )
}
