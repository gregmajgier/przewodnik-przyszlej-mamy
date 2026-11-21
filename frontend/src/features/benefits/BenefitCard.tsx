import { Link } from 'react-router-dom'
import { STATUS_LABEL } from './types'
import type { BenefitMatch } from './types'
import '../../components/a11y.css'
import './benefits.css'

interface Props {
  item: BenefitMatch
  /** Odpowiedź tak/nie na pytanie warunku; strona zapisuje ją przez API. */
  onAnswer: (benefitId: string, conditionId: string, answer: boolean) => void | Promise<void>
  busy?: boolean
}

export default function BenefitCard({ item, onAnswer, busy = false }: Props) {
  const { benefit, match } = item
  const headingId = `benefit-${benefit.id}`
  const why = match.status === 'no' ? match.unmet : match.reasons

  return (
    <article className={`benefit-card is-${match.status}`} aria-labelledby={headingId}>
      <header className="benefit-head">
        <h3 id={headingId}>{benefit.name}</h3>
        <span className={`status-badge is-${match.status}`}>{STATUS_LABEL[match.status]}</span>
      </header>

      {benefit.amount_text && <p className="benefit-amount">{benefit.amount_text}</p>}

      {why.length > 0 && (
        <div className="benefit-why">
          <h4>{match.status === 'no' ? 'Dlaczego nie' : 'Dlaczego'}</h4>
          <ul>
            {why.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {match.status === 'maybe' && match.questions.length > 0 && (
        <div className="benefit-questions" role="group" aria-label={`Pytania o świadczenie ${benefit.name}`}>
          {match.questions.map((q) => (
            <div key={q.condition_id} className="benefit-question">
              <p>{q.text}</p>
              <div className="row">
                <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => void onAnswer(benefit.id, q.condition_id, true)}>
                  Tak
                </button>
                <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => void onAnswer(benefit.id, q.condition_id, false)}>
                  Nie
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {benefit.verify && <p className="muted benefit-verify">Dane do weryfikacji — sprawdź w źródle.</p>}

      <footer className="benefit-foot row">
        {match.status !== 'no' &&
          benefit.form_codes.map((code) => (
            <Link key={code} className="btn" to={`/wnioski/nowy?form=${encodeURIComponent(code)}`}>
              Złóż wniosek{benefit.form_codes.length > 1 ? ` (${code})` : ''}
            </Link>
          ))}
        <a href={benefit.source_url} target="_blank" rel="noopener noreferrer">
          Źródło
          <span className="sr-only"> (otwiera się w nowej karcie)</span>
        </a>
      </footer>
    </article>
  )
}
