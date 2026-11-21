import { useState } from 'react'
import type { FormEvent } from 'react'
import type { AnswerValue, Question } from './types'

interface Props {
  /** Pytania o brakujące dane; zadajemy po jednym (od pierwszego). */
  questions: Question[]
  /** Zapisuje odpowiedź (w profilu — nie pytamy drugi raz); po sukcesie rodzic podaje krótszą listę. */
  onAnswer: (fieldId: string, value: AnswerValue) => Promise<void>
  busy?: boolean
  error?: string | null
}

function QuestionForm({ q, onAnswer, busy }: { q: Question; onAnswer: Props['onAnswer']; busy: boolean }) {
  const [value, setValue] = useState('')
  const inputId = `q-${q.field_id}`
  const empty = value.trim() === ''

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (empty || busy) return
    await onAnswer(q.field_id, value.trim())
  }

  if (q.type === 'bool') {
    return (
      <div className="stack">
        <p id={inputId}>{q.label}</p>
        <div className="row" role="group" aria-labelledby={inputId}>
          <button type="button" className="btn" disabled={busy} onClick={() => void onAnswer(q.field_id, true)}>
            Tak
          </button>
          <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => void onAnswer(q.field_id, false)}>
            Nie
          </button>
        </div>
      </div>
    )
  }

  return (
    <form className="stack" onSubmit={submit} noValidate>
      <div className="field">
        <label htmlFor={inputId}>{q.label}</label>
        {q.type === 'choice' ? (
          <select id={inputId} value={value} onChange={(e) => setValue(e.target.value)}>
            <option value="">Wybierz</option>
            {(q.choices ?? []).map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        ) : (
          <input
            id={inputId}
            type={q.type === 'date' ? 'date' : 'text'}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            autoComplete="off"
          />
        )}
      </div>
      <div className="row">
        <button type="submit" className="btn" disabled={empty || busy}>
          Dalej
        </button>
      </div>
    </form>
  )
}

export default function MissingFieldsStep({ questions, onAnswer, busy = false, error = null }: Props) {
  const q = questions[0]
  if (!q) return null
  return (
    <section className="card stack" aria-labelledby="missing-h">
      <h2 id="missing-h">Brakuje jeszcze danych</h2>
      <p className="muted">
        Pytanie 1 z {questions.length}. Zapamiętamy odpowiedź, więc przy następnym wniosku już o to nie zapytamy.
      </p>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {/* key: po każdej odpowiedzi formularz czyści się dla kolejnego pytania */}
      <QuestionForm key={q.field_id} q={q} onAnswer={onAnswer} busy={busy} />
    </section>
  )
}
