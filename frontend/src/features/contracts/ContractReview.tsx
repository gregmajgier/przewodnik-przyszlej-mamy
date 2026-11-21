import { useId, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { api, ApiError } from '../../lib/api'
import './contracts.css'
import { KIND_LABEL } from './types'
import type { Contract, ContractDraft, ContractKind } from './types'

interface Props {
  draftId: string
  filename: string
  draft: ContractDraft
  onConfirmed: (contract: Contract) => void
  onDiscard: () => void
}

interface FormState {
  kind: ContractKind | ''
  employer_name: string
  employer_address: string
  employer_email: string
  position: string
  fte: string
  gross_monthly: string
  start_date: string
  end_date: string
  term: 'indefinite' | 'fixed' | ''
  voluntary_sickness: 'yes' | 'no' | ''
}

function toForm(d: ContractDraft): FormState {
  return {
    kind: d.kind ?? '',
    employer_name: d.employer_name ?? '',
    employer_address: d.employer_address ?? '',
    employer_email: d.employer_email ?? '',
    position: d.position ?? '',
    fte: d.fte === null ? '' : String(d.fte),
    gross_monthly: d.gross_monthly === null ? '' : String(d.gross_monthly),
    start_date: d.start_date ?? '',
    end_date: d.end_date ?? '',
    term: d.indefinite === true ? 'indefinite' : d.indefinite === false ? 'fixed' : '',
    voluntary_sickness: d.voluntary_sickness === true ? 'yes' : d.voluntary_sickness === false ? 'no' : '',
  }
}

const text = (s: string) => s.trim() || null
const num = (s: string) => {
  const n = Number(s.replace(',', '.'))
  return s.trim() && Number.isFinite(n) ? n : null
}

function toDraft(f: FormState): ContractDraft {
  return {
    kind: f.kind || null,
    employer_name: text(f.employer_name),
    employer_address: text(f.employer_address),
    employer_email: text(f.employer_email),
    position: text(f.position),
    fte: num(f.fte),
    gross_monthly: num(f.gross_monthly),
    start_date: f.start_date || null,
    end_date: f.term === 'fixed' ? f.end_date || null : null,
    indefinite: f.term === '' ? null : f.term === 'indefinite',
    voluntary_sickness: f.voluntary_sickness === '' ? null : f.voluntary_sickness === 'yes',
    missing: [],
  }
}

function Field({
  name,
  label,
  missing,
  wide,
  children,
}: {
  name: string
  label: string
  missing: boolean
  wide?: boolean
  children: (props: { id: string; 'data-missing': boolean; 'aria-describedby'?: string }) => ReactNode
}) {
  const id = useId()
  const hintId = `${id}-hint`
  return (
    <div className={`field${wide ? ' wide' : ''}`} data-field={name}>
      <label htmlFor={id}>{label}</label>
      {children({ id, 'data-missing': missing, 'aria-describedby': missing ? hintId : undefined })}
      {missing && (
        <span id={hintId} className="missing-hint">
          Nie znaleźliśmy tego w umowie — uzupełnij.
        </span>
      )}
    </div>
  )
}

/** Edytowalny formularz z danymi wyciągniętymi z umowy. Nic nie trafia do profilu bez „Zatwierdź”. */
export default function ContractReview({ draftId, filename, draft, onConfirmed, onDiscard }: Props) {
  const [form, setForm] = useState<FormState>(() => toForm(draft))
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const miss = (key: string) =>
    draft.missing.includes(key) && !form[(key === 'indefinite' ? 'term' : key) as keyof FormState]

  const set =
    <K extends keyof FormState>(key: K) =>
    (e: { target: { value: string } }) =>
      setForm((f) => ({ ...f, [key]: e.target.value as FormState[K] }))

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      onConfirmed(
        await api<Contract>(`/api/contracts/${draftId}/confirm`, { method: 'POST', body: toDraft(form) }),
      )
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Nie udało się zatwierdzić umowy.')
      setBusy(false)
    }
  }

  async function discard() {
    setBusy(true)
    try {
      await api(`/api/contracts/${draftId}`, { method: 'DELETE' })
    } catch {
      // szkic i tak wygasa sam po dobie
    }
    onDiscard()
  }

  return (
    <form className="card stack" onSubmit={submit} aria-label={`Sprawdź umowę ${filename}`}>
      <div>
        <h2>Sprawdź, co znaleźliśmy</h2>
        <p className="muted">
          Plik: {filename}. To odczytał asystent AI — może się mylić, więc popraw to, co trzeba. Zapiszemy
          dopiero po Twoim zatwierdzeniu.
        </p>
      </div>
      <div className="contract-form">
        <Field name="kind" label="Rodzaj umowy" missing={miss('kind')}>
          {(p) => (
            <select {...p} value={form.kind} onChange={set('kind')}>
              <option value="">— wybierz —</option>
              {(Object.keys(KIND_LABEL) as ContractKind[]).map((k) => (
                <option key={k} value={k}>
                  {KIND_LABEL[k]}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field name="employer_name" label="Pracodawca (zleceniodawca)" missing={miss('employer_name')}>
          {(p) => <input {...p} value={form.employer_name} onChange={set('employer_name')} />}
        </Field>
        <Field name="employer_address" label="Adres pracodawcy" missing={miss('employer_address')}>
          {(p) => <input {...p} value={form.employer_address} onChange={set('employer_address')} />}
        </Field>
        <Field name="employer_email" label="E-mail pracodawcy (opcjonalnie)" missing={false}>
          {(p) => <input {...p} type="email" value={form.employer_email} onChange={set('employer_email')} />}
        </Field>
        <Field name="position" label="Stanowisko" missing={miss('position')}>
          {(p) => <input {...p} value={form.position} onChange={set('position')} />}
        </Field>
        <Field name="fte" label="Wymiar etatu (0–1, np. 0,5)" missing={miss('fte')}>
          {(p) => <input {...p} inputMode="decimal" value={form.fte} onChange={set('fte')} />}
        </Field>
        <Field name="gross_monthly" label="Wynagrodzenie brutto miesięcznie (zł)" missing={miss('gross_monthly')}>
          {(p) => <input {...p} inputMode="decimal" value={form.gross_monthly} onChange={set('gross_monthly')} />}
        </Field>
        <Field name="start_date" label="Data rozpoczęcia" missing={miss('start_date')}>
          {(p) => <input {...p} type="date" value={form.start_date} onChange={set('start_date')} />}
        </Field>
        <Field name="indefinite" label="Czas trwania" missing={miss('indefinite')}>
          {(p) => (
            <select {...p} value={form.term} onChange={set('term')}>
              <option value="">— wybierz —</option>
              <option value="indefinite">Na czas nieokreślony</option>
              <option value="fixed">Na czas określony</option>
            </select>
          )}
        </Field>
        {form.term === 'fixed' && (
          <Field name="end_date" label="Data zakończenia" missing={miss('end_date')}>
            {(p) => <input {...p} type="date" value={form.end_date} onChange={set('end_date')} />}
          </Field>
        )}
        {(form.kind === 'mandate' || form.kind === 'jdg') && (
          <Field
            name="voluntary_sickness"
            label="Dobrowolne ubezpieczenie chorobowe"
            missing={miss('voluntary_sickness')}
          >
            {(p) => (
              <select {...p} value={form.voluntary_sickness} onChange={set('voluntary_sickness')}>
                <option value="">Nie wiem</option>
                <option value="yes">Tak, mam</option>
                <option value="no">Nie mam</option>
              </select>
            )}
          </Field>
        )}
      </div>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      <div className="row">
        <button type="submit" className="btn" disabled={busy}>
          Zatwierdź
        </button>
        <button type="button" className="btn btn-secondary" disabled={busy} onClick={discard}>
          Odrzuć
        </button>
      </div>
    </form>
  )
}
