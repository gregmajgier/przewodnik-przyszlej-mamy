import { useEffect, useRef, useState } from 'react'
import { ApiError } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { Button } from '../../ui/Button'
import { Icon } from '../../ui/Icon'
import { importDocument, openDocumentPdf } from './documents'
import { KIND_LABEL } from './types'
import type { EmploymentDocument } from './types'
import './attach.css'

/**
 * Krok onboardingu „Umowy” (poglądowo, SYMULACJA): „Załącz umowy” wrzuca przykładowe umowy z e-teczki
 * pracodawcy (umowa o pracę + zlecenie), pokazuje wysyłanie i odczyt przez AI, a potem wyciągnięte dane.
 * Dane naprawdę zapisujemy (POST /api/contracts/documents/{id}/import), więc widzi je panel i asystent AI.
 */

const SPEED = import.meta.env.MODE === 'test' ? 0 : 1
const UPLOAD_MS = 900
const READ_MS = 750

const READ_STEPS = [
  'Odczytuję tekst z PDF-ów',
  'Rozpoznaję rodzaj umowy',
  'Szukam pracodawcy i stanowiska',
  'Sprawdzam okres umowy i wymiar etatu',
  'Szukam zapisów o ubezpieczeniu chorobowym',
]

type Phase = 'idle' | 'uploading' | 'reading' | 'done'

const money = new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN' })

function fteLabel(fte: number | null): string | null {
  if (fte === null) return null
  if (fte >= 1) return 'pełny etat'
  return `${String(fte).replace('.', ',')} etatu`
}

function facts(d: EmploymentDocument): [string, string][] {
  const mandate = d.kind === 'mandate'
  const period = d.indefinite
    ? `od ${formatDate(d.start_date)}, na czas nieokreślony`
    : `od ${formatDate(d.start_date)} do ${d.end_date ? formatDate(d.end_date) : '—'}`
  const rows: [string, string | null][] = [
    ['Rodzaj', KIND_LABEL[d.kind]],
    [mandate ? 'Zleceniodawca' : 'Pracodawca', d.employer_name],
    [mandate ? 'Przedmiot' : 'Stanowisko', d.position],
    ['Wymiar', mandate ? null : fteLabel(d.fte)],
    ['Wynagrodzenie', d.gross_monthly !== null ? `${money.format(d.gross_monthly)} brutto / mies.` : null],
    ['Okres', period],
    ['Chorobowe', mandate ? (d.voluntary_sickness ? 'dobrowolne — tak' : 'brak') : null],
  ]
  return rows.filter((r): r is [string, string] => r[1] !== null)
}

export default function ContractsAttachStep({
  docs,
  onImported,
  onBusyChange,
}: {
  docs: EmploymentDocument[]
  onImported: (docs: EmploymentDocument[]) => void
  onBusyChange: (busy: boolean) => void
}) {
  const alreadyDone = docs.length > 0 && docs.every((d) => d.contract_id)
  const [phase, setPhase] = useState<Phase>(alreadyDone ? 'done' : 'idle')
  const [uploaded, setUploaded] = useState(0) // ile plików już „wysłanych”
  const [readStep, setReadStep] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const alive = useRef(true)

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
    }
  }, [])

  const wait = (ms: number) => new Promise((r) => window.setTimeout(r, ms * SPEED))

  async function attach() {
    setError(null)
    setUploaded(0)
    setReadStep(0)
    setPhase('uploading')
    onBusyChange(true)
    try {
      for (let i = 0; i < docs.length; i++) {
        await wait(UPLOAD_MS)
        if (!alive.current) return
        setUploaded(i + 1)
      }
      setPhase('reading')
      // zapis w tle, równolegle z „odczytem” — na końcu czekamy na oba
      const saving = Promise.all(docs.map((d) => (d.contract_id ? Promise.resolve(null) : importDocument(d.id))))
      for (let s = 1; s <= READ_STEPS.length; s++) {
        await wait(READ_MS)
        if (!alive.current) return
        setReadStep(s)
      }
      const saved = await saving
      if (!alive.current) return
      onImported(docs.map((d, i) => ({ ...d, contract_id: saved[i]?.id ?? d.contract_id })))
      setPhase('done')
    } catch (e) {
      if (!alive.current) return
      setError(e instanceof ApiError ? e.detail : 'Nie udało się dodać umów. Spróbuj ponownie.')
      setPhase('idle')
    } finally {
      if (alive.current) onBusyChange(false)
    }
  }

  function preview(id: string) {
    void openDocumentPdf(id).catch((e) =>
      setError(e instanceof ApiError ? e.detail : 'Nie udało się otworzyć umowy.'),
    )
  }

  if (docs.length === 0) return null

  return (
    <div className="attach rise" style={{ ['--i' as string]: 3 }}>
      {phase === 'idle' && (
        <div className="attach-drop">
          <span className="attach-drop-icon" aria-hidden="true">
            <Icon name="upload" size={28} />
          </span>
          <p className="attach-drop-text">
            Umowa o pracę, zlecenie albo B2B — w PDF lub jako zdjęcie. AI odczyta z nich najważniejsze dane.
          </p>
          <Button leading="upload" onClick={() => void attach()}>
            Załącz umowy
          </Button>
          <p className="attach-sim">
            <span className="badge-sim">SYMULACJA</span>
            <span>W demo załączymy przykładowe umowy z Twojej e-teczki.</span>
          </p>
        </div>
      )}

      {(phase === 'uploading' || phase === 'reading') && (
        <div className="card stack attach-work" aria-live="polite">
          <ul className="attach-files" aria-label="Załączone pliki">
            {docs.map((d, i) => {
              const done = i < uploaded
              const active = phase === 'uploading' && i === uploaded
              return (
                <li key={d.id} className={done ? 'is-done' : active ? 'is-active' : ''}>
                  <Icon name="doc" size={20} />
                  <span className="attach-file-main">
                    <span className="attach-file-name">{d.filename}</span>
                    <span className="attach-bar" aria-hidden="true">
                      <span className="attach-bar-fill" />
                    </span>
                  </span>
                  <span className="attach-file-state">{done ? 'Wysłano' : active ? 'Wysyłam…' : 'Czeka'}</span>
                </li>
              )
            })}
          </ul>
          {phase === 'reading' && (
            <div className="attach-ai">
              <p className="attach-ai-head">
                <Icon name="sparkle" size={18} /> AI czyta Twoje umowy <span className="badge-sim">SYMULACJA</span>
              </p>
              <ol className="attach-steps">
                {READ_STEPS.map((label, i) => {
                  const done = i < readStep
                  const active = i === readStep
                  return (
                    <li key={label} className={done ? 'is-done' : active ? 'is-active' : ''}>
                      <span className="attach-step-mark" aria-hidden="true">
                        {done ? (
                          <Icon name="check" size={14} stroke={2.6} />
                        ) : active ? (
                          <Icon name="refresh" size={14} className="spin" />
                        ) : null}
                      </span>
                      {label}
                    </li>
                  )
                })}
              </ol>
            </div>
          )}
        </div>
      )}

      {phase === 'done' && (
        <div className="stack">
          <p className="attach-done" role="status">
            <Icon name="checkCircle" size={20} /> Odczytaliśmy {docs.length === 1 ? 'umowę' : `${docs.length} umowy`}{' '}
            i dodaliśmy je do Twoich umów
          </p>
          {docs.map((d) => (
            <article key={d.id} className="card attach-result" aria-label={d.title}>
              <header className="attach-result-head">
                <span className="icon-tile">
                  <Icon name="docCheck" size={22} />
                </span>
                <span className="attach-result-title">
                  <strong>{d.title}</strong>
                  <span className="muted">{d.filename}</span>
                </span>
              </header>
              <dl className="facts attach-facts">
                {facts(d).map(([k, v]) => (
                  <div key={k} className="attach-fact">
                    <dt>{k}</dt>
                    <dd>{v}</dd>
                  </div>
                ))}
              </dl>
              <button
                type="button"
                className="doc-preview"
                aria-label={`Podgląd PDF: ${d.title}`}
                onClick={() => preview(d.id)}
              >
                <Icon name="eye" size={16} /> Podgląd PDF
              </button>
            </article>
          ))}
          <div className="flow-note" style={{ marginTop: 0 }}>
            <Icon name="lock" size={18} />
            <span>
              Plik widzisz tylko Ty. Drugi rodzic i asystent AI widzą pracodawcę, stanowisko i okres umowy — bez
              wynagrodzenia. Dane poprawisz w zakładce Umowy.
            </span>
          </div>
        </div>
      )}

      {error && (
        <p role="alert" className="alert" style={{ marginTop: '1rem' }}>
          <Icon name="alert" size={20} />
          {error}
        </p>
      )}
    </div>
  )
}
