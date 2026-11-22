import { useState } from 'react'
import type { FormEvent } from 'react'
import { Button } from '../../ui/Button'
import { Icon } from '../../ui/Icon'
import { DateField, Select } from '../../ui/controls'
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

  async function submit(e?: FormEvent) {
    e?.preventDefault()
    if (empty || busy) return
    await onAnswer(q.field_id, value.trim())
  }

  if (q.type === 'bool') {
    return (
      <div className="stack">
        <p id={inputId} className="question-text">
          {q.label}
        </p>
        <div className="bsheet-q-actions" role="group" aria-labelledby={inputId}>
          <button type="button" className="answer-btn" disabled={busy} onClick={() => void onAnswer(q.field_id, true)}>
            Tak
          </button>
          <button type="button" className="answer-btn" disabled={busy} onClick={() => void onAnswer(q.field_id, false)}>
            Nie
          </button>
        </div>
      </div>
    )
  }

  return (
    <form className="stack" onSubmit={submit} noValidate>
      {q.type === 'choice' ? (
        <Select
          id={inputId}
          label={q.label}
          value={value}
          onChange={setValue}
          options={(q.choices ?? []).map((c) => ({ value: c, label: c }))}
        />
      ) : q.type === 'date' ? (
        <DateField id={inputId} label={q.label} value={value} onChange={setValue} />
      ) : (
        <label className="field" htmlFor={inputId}>
          {q.label}
          <input id={inputId} value={value} onChange={(e) => setValue(e.target.value)} autoComplete="off" />
        </label>
      )}
      <Button type="submit" block disabled={empty || busy} icon="arrowRight">
        Dalej
      </Button>
    </form>
  )
}

export default function MissingFieldsStep({ questions, onAnswer, busy = false, error = null }: Props) {
  const q = questions[0]
  if (!q) return null
  return (
    <section className="card question-card stack" aria-labelledby="missing-h">
      <div className="question-head">
        <span className="icon-tile tone-butter">
          <Icon name="pen" size={22} />
        </span>
        <div>
          <h2 id="missing-h">Brakuje jeszcze {questions.length === 1 ? 'jednej informacji' : `${questions.length} informacji`}</h2>
          <p className="muted small">
            Pytanie 1 z {questions.length}. Zapamiętamy odpowiedź i przy kolejnym wniosku już o to nie zapytamy.
          </p>
        </div>
      </div>
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
