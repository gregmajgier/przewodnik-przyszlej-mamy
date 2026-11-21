import { useEffect, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../../lib/api'
import './chat.css'
import { EXAMPLE_QUESTIONS } from './examples'
import { Message } from './Message'
import { useChatStream } from './useChatStream'

const MAX_CHARS = 2000

export default function ChatPage() {
  const { messages, sending, notice, activity, send, reset } = useChatStream()
  const [draft, setDraft] = useState('')
  const [demo, setDemo] = useState(false)
  const [params, setParams] = useSearchParams()
  const autoSent = useRef(false)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    api<{ mode: 'demo' | 'live' }>('/api/ai/status')
      .then((s) => {
        if (!cancelled) setDemo(s.mode === 'demo')
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  // Pytanie z kafelka na dashboardzie (?q=...): wysyłamy raz, potem czyścimy adres.
  useEffect(() => {
    const q = params.get('q')
    if (q && !autoSent.current) {
      autoSent.current = true
      setParams({}, { replace: true })
      void send(q)
    }
  }, [params, send, setParams])

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: 'end' })
  }, [messages, activity])

  function submit(e?: FormEvent) {
    e?.preventDefault()
    const text = draft.trim()
    if (!text || sending) return
    setDraft('')
    void send(text)
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  const empty = messages.length === 0

  return (
    <div className="chat stack">
      <div className="row chat-head">
        <h1>Zapytaj mRodzinę</h1>
        {demo && (
          <span className="badge-sim" title="Asystent AI nie jest podłączony do modelu">
            TRYB DEMO
          </span>
        )}
        <button type="button" className="btn btn-secondary chat-new" onClick={reset} disabled={empty && !notice}>
          Nowa rozmowa
        </button>
      </div>

      <section className="chat-window card" aria-label="Rozmowa" aria-live="polite" aria-busy={sending}>
        {empty && (
          <div className="chat-empty stack">
            <p>
              Zapytaj o urlopy, zasiłki, żłobek czy przedszkole. Odpowiadam na podstawie przepisów i danych
              Twojej rodziny — i zawsze podaję, skąd to wiem.
            </p>
            <div className="chat-examples" role="group" aria-label="Przykładowe pytania">
              {EXAMPLE_QUESTIONS.map((q) => (
                <button key={q} type="button" className="chat-chip" onClick={() => void send(q)} disabled={sending}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m) => (
          <Message key={m.id} message={m} />
        ))}
        {activity && (
          <p className="chat-activity muted" role="status">
            {activity}
          </p>
        )}
        <div ref={endRef} />
      </section>

      {notice && (
        <p className="notice" role="status" aria-label="Komunikat">
          {notice}
        </p>
      )}

      <form className="chat-form" onSubmit={submit}>
        <div className="field chat-field">
          <label htmlFor="chat-input">Twoje pytanie</label>
          <textarea
            id="chat-input"
            rows={2}
            maxLength={MAX_CHARS}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Np. ile trwa urlop rodzicielski?"
          />
        </div>
        <button type="submit" className="btn" disabled={sending || draft.trim() === ''}>
          Wyślij
        </button>
      </form>
      <p className="muted chat-disclaimer">
        To informacja, nie porada prawna. W sprawach spornych zapytaj w urzędzie, ZUS lub PUP. Nie wpisuj numeru
        PESEL ani danych finansowych.
      </p>
    </div>
  )
}
