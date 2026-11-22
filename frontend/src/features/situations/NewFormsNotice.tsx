import { useEffect, useState } from 'react'
import { Button } from '../../ui/Button'
import { loadNewForms, plWnioski } from './newForms'
import type { HardSituation, NewForm } from './newForms'
import './situations.css'

type Load = { state: 'loading' } | { state: 'error' } | { state: 'ok'; forms: NewForm[] }

/**
 * Spokojny komunikat po zgłoszeniu trudnej sytuacji: ile i jakich wniosków rodzic może teraz złożyć.
 * Bez gratulacji i wykrzykników; kolory z tokenów (w trybie mono same robią się szare).
 */
export function NewFormsNotice({ situation, childId }: { situation: HardSituation; childId: string }) {
  const key = `${situation}:${childId}`
  const [result, setResult] = useState<{ key: string; load: Load } | null>(null)

  useEffect(() => {
    let cancelled = false
    loadNewForms(situation, childId)
      .then((forms) => !cancelled && setResult({ key, load: { state: 'ok', forms } }))
      .catch(() => !cancelled && setResult({ key, load: { state: 'error' } }))
    return () => {
      cancelled = true
    }
  }, [key, situation, childId])

  const load: Load = result && result.key === key ? result.load : { state: 'loading' }

  return (
    <section className="card sit-forms" role="status" aria-label="Wnioski po zgłoszeniu">
      {load.state === 'loading' && <p className="sit-muted">Sprawdzam, jakie wnioski możesz teraz złożyć…</p>}
      {load.state === 'error' && (
        <p className="sit-muted">Nie udało się teraz sprawdzić wniosków. Zobaczysz je w zakładce „Wnioski”.</p>
      )}
      {load.state === 'ok' && load.forms.length === 0 && (
        <p className="sit-muted">Przy tej sytuacji nie ma nowych wniosków do złożenia.</p>
      )}
      {load.state === 'ok' && load.forms.length > 0 && (
        <>
          <h3 className="sit-forms-title">Po tym zgłoszeniu możesz złożyć {plWnioski(load.forms.length)}:</h3>
          <ul className="sit-forms-list">
            {load.forms.map((f) => (
              <li key={f.code}>
                <span className="sit-forms-name">
                  {f.name} <span className="sit-nowrap">({f.code})</span>
                </span>
                {f.institution && <span className="sit-muted">Składasz: {f.institution}</span>}
                {f.action.kind === 'wizard' && (
                  <Button variant="secondary" size="sm" to={f.action.href}>
                    Przygotuj wniosek
                  </Button>
                )}
                {f.action.kind === 'pdf' && (
                  <Button variant="secondary" size="sm" leading="download" href={f.action.href} target="_blank" rel="noopener noreferrer">
                    Pobierz pusty wniosek (PDF)
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
