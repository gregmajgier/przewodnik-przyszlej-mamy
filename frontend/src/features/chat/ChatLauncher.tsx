import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import './chat.css'
import { EXAMPLE_QUESTIONS } from './examples'

/** Kafelek dashboardu „Zapytaj mRodzinę”: pole pytania + przykłady; przenosi do /czat z pytaniem. */
export default function ChatLauncher() {
  const [q, setQ] = useState('')
  const navigate = useNavigate()

  const ask = (question: string) => {
    const text = question.trim()
    if (text) navigate(`/czat?q=${encodeURIComponent(text)}`)
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    ask(q)
  }

  return (
    <section className="card chat-launcher stack" aria-labelledby="chat-launcher-title">
      <h2 id="chat-launcher-title">Zapytaj mRodzinę</h2>
      <p className="muted">Pytaj o urlopy, zasiłki, żłobek i przedszkole — odpowiem z przepisami i linkami.</p>
      <form className="row chat-launcher-form" onSubmit={submit}>
        <div className="field chat-field">
          <label htmlFor="chat-launcher-input">Zadaj pytanie</label>
          <input
            id="chat-launcher-input"
            type="text"
            value={q}
            maxLength={2000}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Np. ile trwa urlop rodzicielski?"
          />
        </div>
        <button type="submit" className="btn" disabled={q.trim() === ''}>
          Zapytaj
        </button>
      </form>
      <div className="chat-examples" role="group" aria-label="Przykładowe pytania">
        {EXAMPLE_QUESTIONS.slice(0, 2).map((ex) => (
          <button key={ex} type="button" className="chat-chip" onClick={() => ask(ex)}>
            {ex}
          </button>
        ))}
      </div>
    </section>
  )
}
