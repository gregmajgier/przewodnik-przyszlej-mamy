import { Link } from 'react-router-dom'
import { formatDate } from '../../lib/format'
import { STATUS_LABEL } from './format'
import type { BenefitMatch } from './types'
import './benefits.css'

interface Props {
  item: BenefitMatch
  onAnswer: (benefitId: string, conditionId: string, answer: boolean) => void
  busy?: boolean
}

export default function BenefitCard({ item, onAnswer, busy = false }: Props) {
  const { benefit, match, deadline_date } = item
  const form = benefit.form_codes[0]
  const why =
    match.status === 'fits'
      ? `Pasuje, bo ${match.reasons.join(' i ')}.`
      : match.status === 'maybe'
        ? match.reasons.length
          ? `Na razie wiemy, że ${match.reasons.join(' i ')}. Potrzebujemy jeszcze twojej odpowiedzi.`
          : 'Potrzebujemy jeszcze twojej odpowiedzi.'
        : match.unmet.join(' ')

  return (
    <article className={`bf-card bf-${match.status}`} aria-labelledby={`bf-${benefit.id}`}>
      <div className="bf-head">
        <h3 id={`bf-${benefit.id}`}>{benefit.name}</h3>
        <span className={`bf-badge bf-badge-${match.status}`}>{STATUS_LABEL[match.status]}</span>
      </div>
      <p className="bf-why">{why}</p>
      {match.status === 'maybe' && match.questions.length > 0 && (
        <ul className="bf-questions">
          {match.questions.map((q) => (
            <li key={q.condition_id}>
              <span id={`q-${benefit.id}-${q.condition_id}`}>{q.text}</span>
              <span className="bf-yesno" role="group" aria-labelledby={`q-${benefit.id}-${q.condition_id}`}>
                <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => onAnswer(benefit.id, q.condition_id, true)}>
                  Tak
                </button>
                <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => onAnswer(benefit.id, q.condition_id, false)}>
                  Nie
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
      {match.status !== 'no' && (
        <>
          <p>{benefit.description}</p>
          {benefit.amount_text && (
            <p className="bf-amount">
              <strong>{benefit.amount_text}</strong>
            </p>
          )}
          {deadline_date && <p className="bf-deadline">Termin: {formatDate(deadline_date)}</p>}
        </>
      )}
      {benefit.verify && (
        <p className="bf-verify">Dane do weryfikacji — potwierdź w źródle, zanim złożysz wniosek.</p>
      )}
      <div className="bf-actions">
        {match.status !== 'no' && form && (
          <Link className="btn" to={`/wnioski/nowy?form=${encodeURIComponent(form)}`}>
            Złóż wniosek
          </Link>
        )}
        <a href={benefit.source_url} target="_blank" rel="noopener noreferrer">
          Źródło
        </a>
      </div>
    </article>
  )
}
