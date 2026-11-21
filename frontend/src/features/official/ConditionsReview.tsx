import { Icon } from '../../ui/Icon'
import type { Condition } from './types'

const PROFILE_KEY_LABEL: Record<string, string> = {
  residence_months: 'okres zameldowania',
  child_in_public_nursery: 'dziecko w publicznym żłobku',
  child_in_private_nursery: 'dziecko w niepublicznym żłobku',
  child_in_preschool: 'dziecko w przedszkolu',
  parent_employed: 'rodzic pracuje',
  large_family_card: 'Karta Dużej Rodziny',
  single_parent: 'samotny rodzic',
  pays_taxes_in_municipality: 'PIT w gminie',
}

/** Edytowalna lista warunków wyodrębnionych z „Dodatkowych wymogów”. */
export default function ConditionsReview({
  conditions,
  onChange,
}: {
  conditions: Condition[]
  onChange: (next: Condition[]) => void
}) {
  function update(i: number, patch: Partial<Condition>) {
    onChange(conditions.map((c, j) => (j === i ? { ...c, ...patch } : c)))
  }

  function add() {
    onChange([...conditions, { id: `nowy-${Date.now().toString(36)}`, text: '', kind: 'ask', question: '', profile_key: null }])
  }

  return (
    <div className="stack">
      {conditions.length === 0 && <p className="muted">Brak warunków. Możesz dodać je ręcznie.</p>}
      {conditions.length > 0 && (
        <ol className="off-conds" aria-label="Warunki">
          {conditions.map((c, i) => {
            const auto = c.kind === 'auto' && c.profile_key
            return (
              <li key={c.id} className="off-cond">
                <span className="off-cond-n" aria-hidden="true">
                  {i + 1}
                </span>
                <div className="off-cond-body">
                  <div className="field">
                    <label htmlFor={`cond-text-${i}`}>Warunek {i + 1}</label>
                    <input id={`cond-text-${i}`} value={c.text} onChange={(e) => update(i, { text: e.target.value })} />
                  </div>
                  <div className="field">
                    <label htmlFor={`cond-q-${i}`}>Pytanie do rodzica (tak/nie)</label>
                    <input id={`cond-q-${i}`} value={c.question ?? ''} onChange={(e) => update(i, { question: e.target.value })} />
                  </div>
                  <p className={`off-cond-how ${auto ? 'is-auto' : ''}`}>
                    <Icon name={auto ? 'sparkle' : 'chat'} size={15} />
                    {auto
                      ? `Sprawdzimy sami z profilu rodziny: ${PROFILE_KEY_LABEL[c.profile_key!] ?? c.profile_key}`
                      : 'Rodzic odpowie na pytanie tak/nie'}
                  </p>
                </div>
                <button
                  className="icon-btn off-cond-del"
                  type="button"
                  aria-label={`Usuń warunek ${i + 1}`}
                  onClick={() => onChange(conditions.filter((_, j) => j !== i))}
                >
                  <Icon name="trash" size={18} />
                </button>
              </li>
            )
          })}
        </ol>
      )}
      <button className="off-add" type="button" onClick={add}>
        <Icon name="plus" size={18} />
        Dodaj warunek ręcznie
      </button>
    </div>
  )
}
