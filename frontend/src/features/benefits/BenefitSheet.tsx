import { Button } from '../../ui/Button'
import { Icon } from '../../ui/Icon'
import { Pill } from '../../ui/controls'
import { Sheet } from '../../ui/Sheet'
import { catMeta, categoryOf } from './categories'
import { STATUS_LABEL } from './types'
import type { BenefitMatch, MatchStatus } from './types'
import './benefits.css'

export const STATUS_TONE: Record<MatchStatus, 'green' | 'amber' | 'neutral'> = { fits: 'green', maybe: 'amber', no: 'neutral' }

interface Props {
  item: BenefitMatch | null
  onClose: () => void
  onAnswer: (benefitId: string, conditionId: string, value: boolean) => void | Promise<void>
  busy?: boolean
}

/** Szczegóły świadczenia w arkuszu: kwota, dlaczego pasuje, pytania, jak złożyć, przycisk wniosku i pytanie do czatu. */
export function BenefitSheet({ item, onClose, onAnswer, busy = false }: Props) {
  if (!item) return null
  const { benefit, match } = item
  const cat = catMeta(categoryOf(benefit))
  const why = match.status === 'no' ? match.unmet : match.reasons
  const form = match.status !== 'no' ? benefit.form_codes[0] : undefined

  return (
    <Sheet
      open
      onClose={onClose}
      size="lg"
      title={benefit.name}
      subtitle={
        <span className="row" style={{ gap: '0.4rem', marginTop: '0.25rem' }}>
          <Pill tone={STATUS_TONE[match.status]} dot>
            {STATUS_LABEL[match.status]}
          </Pill>
          <Pill>{cat.label}</Pill>
        </span>
      }
      footer={
        <>
          <Button
            variant="secondary"
            leading="sparkle"
            to="/czat"
            state={{ q: `Opowiedz mi o świadczeniu: ${benefit.name}. Czy nam przysługuje i jak je dostać?`, autoSend: true }}
          >
            Zapytaj
          </Button>
          {form ? (
            <Button to={`/wnioski/nowy?form=${encodeURIComponent(form)}`} icon="arrowRight">
              Złóż wniosek
            </Button>
          ) : (
            <Button href={benefit.source_url} target="_blank" rel="noopener noreferrer" icon="external">
              Źródło
            </Button>
          )}
        </>
      }
    >
      <div className="bsheet">
        {benefit.amount_text && (
          <div className={`bsheet-amount tone-${cat.tone}`}>
            <Icon name={cat.icon} size={26} />
            <span>{benefit.amount_text}</span>
          </div>
        )}
        <p className="bsheet-desc">{benefit.description}</p>

        {why.length > 0 && (
          <section>
            <h3>{match.status === 'no' ? 'Dlaczego nie teraz' : 'Dlaczego Wam pasuje'}</h3>
            <ul className="bsheet-why">
              {why.map((r) => (
                <li key={r}>
                  <Icon name={match.status === 'no' ? 'minus' : 'check'} size={18} stroke={2.2} />
                  {r}
                </li>
              ))}
            </ul>
          </section>
        )}

        {match.status === 'maybe' && match.questions.length > 0 && (
          <section className="bsheet-questions" aria-label={`Pytania o świadczenie ${benefit.name}`}>
            <h3>Odpowiedz, a sprawdzimy do końca</h3>
            {match.questions.map((q) => (
              <div key={q.condition_id} className="bsheet-q">
                <p>{q.text}</p>
                <div className="bsheet-q-actions">
                  <button type="button" className="answer-btn" disabled={busy} onClick={() => void onAnswer(benefit.id, q.condition_id, true)}>
                    Tak
                  </button>
                  <button type="button" className="answer-btn" disabled={busy} onClick={() => void onAnswer(benefit.id, q.condition_id, false)}>
                    Nie
                  </button>
                </div>
              </div>
            ))}
            <p className="small muted">Zapamiętamy odpowiedź — nie zapytamy drugi raz.</p>
          </section>
        )}

        <section>
          <h3>Jak to załatwić</h3>
          <p>{benefit.how_to_apply}</p>
          {benefit.extra_text && <p className="bsheet-extra">{benefit.extra_text}</p>}
        </section>

        <a className="bsheet-source" href={benefit.source_url} target="_blank" rel="noopener noreferrer">
          <Icon name="external" size={16} /> Oficjalne źródło
          <span className="sr-only"> (otwiera się w nowej karcie)</span>
        </a>
      </div>
    </Sheet>
  )
}
