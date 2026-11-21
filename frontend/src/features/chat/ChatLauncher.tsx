import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { MAX_MESSAGE_CHARS } from './useChatStream'
import './chat.css'

const EXAMPLES = ['Jak działa urlop macierzyński?', 'Jak zapisać dziecko do przedszkola?']

/** Kafelek dashboardu „Zapytaj mRodzinę”: pole pytania i przykłady; odpowiedź pokazuje strona /czat. */
export function ChatLauncher() {
  const [draft, setDraft] = useState('')
  const navigate = useNavigate()

  function ask(question: string) {
    const q = question.trim()
    navigate('/czat', q ? { state: { q } } : undefined)
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    ask(draft)
  }

  return (
    <section className="card chat-launcher" aria-labelledby="chat-launcher-title">
      <h2 id="chat-launcher-title">Zapytaj mRodzinę</h2>
      <p className="muted">Pytaj o przepisy, zasiłki i zapisy. Odpowiadam ze źródłami.</p>
      <form className="row" onSubmit={submit}>
        <label className="field chat-launcher-field" htmlFor="chat-launcher-input">
          <span className="chat-sr">Twoje pytanie</span>
          <input
            id="chat-launcher-input"
            type="text"
            value={draft}
            maxLength={MAX_MESSAGE_CHARS}
            placeholder="Co chcesz wiedzieć?"
            onChange={(e) => setDraft(e.target.value)}
          />
        </label>
        <button type="submit" className="btn">
          Zapytaj
        </button>
      </form>
      <ul className="chat-examples" aria-label="Przykładowe pytania">
        {EXAMPLES.map((q) => (
          <li key={q}>
            <button type="button" className="chat-chip" onClick={() => ask(q)}>
              {q}
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
