import { useEffect, useState } from 'react'
import type { ChecklistItem, ChecklistKind, SituationDetail } from './jaskolkaApi'

const KIND_LABEL: Record<ChecklistKind, string> = {
  right: 'Przysługuje ci',
  document: 'Dokument',
  step: 'Krok',
}

const storageKey = (situationId: string) => `jaskolka:checked:${situationId}`

function readChecked(situationId: string): string[] {
  try {
    const raw = sessionStorage.getItem(storageKey(situationId))
    const parsed: unknown = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === 'string') : []
  } catch {
    return []
  }
}

function writeChecked(situationId: string, ids: string[]) {
  try {
    sessionStorage.setItem(storageKey(situationId), JSON.stringify(ids))
  } catch {
    // pamięć sesji niedostępna: odhaczanie działa tylko do odświeżenia strony
  }
}

function Item({ item, checked, onToggle }: { item: ChecklistItem; checked: boolean; onToggle: () => void }) {
  const inputId = `jk-item-${item.id}`
  return (
    <li className={`jk-item${checked ? ' jk-item-done' : ''}`}>
      <div className="jk-item-check">
        <input id={inputId} type="checkbox" checked={checked} onChange={onToggle} />
        <label htmlFor={inputId}>
          <span className="jk-kind">{KIND_LABEL[item.kind]}</span>
          <span className="jk-item-title">{item.title}</span>
        </label>
      </div>
      <p className="jk-item-body">{item.body}</p>
      {item.deadline_text && (
        <p className="jk-deadline">
          <strong>Termin:</strong> {item.deadline_text}
        </p>
      )}
      {item.form_codes.length > 0 && (
        <p className="jk-forms">
          <strong>Formularz:</strong> {item.form_codes.join(', ')}
        </p>
      )}
      {item.verify && (
        <p className="jk-verify">Ta informacja może wymagać potwierdzenia. Sprawdź ją w źródle lub zapytaj w urzędzie.</p>
      )}
      <p className="jk-source">
        <a href={item.source_url} target="_blank" rel="noopener noreferrer">
          Źródło<span className="jk-sr"> (otwiera się w nowej karcie)</span>
        </a>
      </p>
    </li>
  )
}

export function Checklist({ situation }: { situation: SituationDetail }) {
  const [checked, setChecked] = useState<string[]>(() => readChecked(situation.id))

  useEffect(() => {
    setChecked(readChecked(situation.id))
  }, [situation.id])

  function toggle(id: string) {
    setChecked((prev) => {
      const next = prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
      writeChecked(situation.id, next)
      return next
    })
  }

  return (
    <section aria-labelledby="jk-checklist-title" className="jk-fade">
      <h1 id="jk-checklist-title">{situation.label}</h1>
      <p className="jk-lead">{situation.intro}</p>
      <p className="jk-note">
        Odhaczenia zostają tylko w tej karcie przeglądarki i znikają po jej zamknięciu. Nic nie zapisujemy na serwerze.
      </p>
      <ul className="jk-list">
        {situation.checklist.map((item) => (
          <Item key={item.id} item={item} checked={checked.includes(item.id)} onToggle={() => toggle(item.id)} />
        ))}
      </ul>
    </section>
  )
}
