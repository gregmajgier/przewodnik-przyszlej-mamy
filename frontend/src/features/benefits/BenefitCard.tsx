import { Link } from 'react-router-dom'
import { applyActions } from '../applications/formLabels'
import type { FormEntry } from '../applications/types'
import { STATUS_LABEL } from './types'
import type { BenefitMatch } from './types'
import '../../components/a11y.css'
import './benefits.css'

interface Props {
  item: BenefitMatch
  /** Odpowiedź tak/nie na pytanie warunku; strona zapisuje ją przez API. */
  onAnswer: (benefitId: string, conditionId: string, answer: boolean) => void | Promise<void>
  busy?: boolean
  /** Katalog wniosków (do etykiet „dla pracodawcy”, „do ZUS”); bez niego przyciski mają ogólny podpis. */
  forms?: FormEntry[]
  /** Uzasadnienia wspólne dla całej grupy — pokazane raz nad listą, więc tu je pomijamy. */
  hideReasons?: string[]
}

export default function BenefitCard({ item, onAnswer, busy = false, forms = [], hideReasons = [] }: Props) {
  const { benefit, match } = item
  const headingId = `benefit-${benefit.id}`
  const all = match.status === 'no' ? match.unmet : match.reasons
  const own = all.filter((r) => !hideReasons.includes(r))
  const lead = own[0]
  const actions = match.status === 'no' ? [] : applyActions(benefit.form_codes, forms)
  const hasDetails = benefit.description || benefit.how_to_apply || all.length > 1 || benefit.verify

  return (
    <article className={`benefit-card is-${match.status}`} aria-labelledby={headingId}>
      <header className="benefit-head">
        <h3 id={headingId}>{benefit.name}</h3>
        <span className={`status-badge is-${match.status}`}>{STATUS_LABEL[match.status]}</span>
      </header>

      {benefit.amount_text && <p className="benefit-amount">{benefit.amount_text}</p>}
      {benefit.form_codes.length > 0 && match.status !== 'no' && <p className="benefit-kind">Wymaga złożenia wniosku</p>}
      {lead && (
        <p className="benefit-lead">
          <span className="muted">{match.status === 'no' ? 'Dlaczego nie: ' : 'Dlaczego: '}</span>
          {lead}
        </p>
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

      {hasDetails && (
        <details className="benefit-details">
          <summary>Szczegóły</summary>
          <div className="stack benefit-details-body">
            {benefit.description && <p>{benefit.description}</p>}
            {all.length > 1 && (
              <ul>
                {all.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            )}
            {benefit.how_to_apply && (
              <p>
                <strong>Jak skorzystać: </strong>
                {benefit.how_to_apply}
              </p>
            )}
            {benefit.verify && <p className="muted">Dane do weryfikacji, sprawdź je w źródle.</p>}
          </div>
        </details>
      )}

      <footer className="benefit-foot row">
        {actions.map((a) => (
          <Link key={a.code} className="btn" to={`/wnioski/nowy?form=${encodeURIComponent(a.code)}`}>
            {a.label}
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
