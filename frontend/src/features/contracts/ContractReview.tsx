import { useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { api, ApiError } from '../../lib/api'
import './contracts.css'
import { KIND_LABEL } from './types'
import type { Contract, ContractDraft, ContractKind, ScanResult } from './types'
import { decimalToNumber } from '../../lib/numeric'
import { openNativePicker } from '../../ui/nativePicker'

const LABELS: Record<string, string> = {
  kind: 'Rodzaj umowy',
  employer_name: 'Pracodawca / zleceniodawca',
  employer_address: 'Adres pracodawcy',
  employer_email: 'E-mail pracodawcy (kadry)',
  position: 'Stanowisko / przedmiot umowy',
  fte: 'Wymiar etatu (np. 1 lub 0,5)',
  gross_monthly: 'Wynagrodzenie brutto miesięcznie (zł)',
  start_date: 'Data rozpoczęcia',
  end_date: 'Data zakończenia',
  indefinite: 'Na czas nieokreślony',
  voluntary_sickness: 'Dobrowolne ubezpieczenie chorobowe',
}

function toNumber(v: string): number | null {
  return decimalToNumber(v)
}

function Field({ name, missing, children }: { name: string; missing: boolean; children: ReactNode }) {
  return (
    <div className={`field${missing ? ' field-missing' : ''}`} data-testid={`field-${name}`}>
      <label htmlFor={`contract-${name}`}>{LABELS[name]}</label>
      {children}
      {missing && (
        <span className="field-missing-note" id={`contract-${name}-note`}>
          Nie udało się odczytać. Uzupełnij.
        </span>
      )}
    </div>
  )
}

/** Formularz do przejrzenia i poprawienia danych odczytanych przez AI. Zapis dopiero po „Zatwierdź”. */
export function ContractReview({
  scan,
  onConfirmed,
  onCancel,
}: {
  scan: ScanResult
  onConfirmed: (c: Contract) => void
  onCancel?: () => void
}) {
  const [d, setD] = useState<ContractDraft>(scan.draft)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const missing = new Set(scan.draft.missing)

  function set<K extends keyof ContractDraft>(key: K, value: ContractDraft[K]) {
    setD((prev) => ({ ...prev, [key]: value }))
  }

  function inputProps(name: string) {
    const isMissing = missing.has(name)
    return {
      id: `contract-${name}`,
      'aria-invalid': isMissing || undefined,
      'aria-describedby': isMissing ? `contract-${name}-note` : undefined,
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const body = { ...d, missing: [] }
      const contract = await api<Contract>(`/api/contracts/${scan.draft_id}/confirm`, { method: 'POST', body })
      onConfirmed(contract)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Nie udało się zapisać umowy.')
      setBusy(false)
    }
  }

  return (
    <form className="card stack" onSubmit={submit} aria-label="Sprawdź dane umowy">
      <h2>Sprawdź dane umowy</h2>
      <p className="muted">
        Odczytaliśmy plik „{scan.filename}”. Sprawdź dane i popraw, jeśli coś się nie zgadza.
        {missing.size > 0 && ' Pola podświetlone trzeba uzupełnić.'} Zapiszemy je dopiero po
        zatwierdzeniu.
      </p>
      <div className="contract-form">
        <Field name="kind" missing={missing.has('kind')}>
          <select
            {...inputProps('kind')}
            value={d.kind ?? ''}
            onChange={(e) => set('kind', (e.target.value || null) as ContractKind | null)}
          >
            <option value="">Wybierz</option>
            {(Object.keys(KIND_LABEL) as ContractKind[]).map((k) => (
              <option key={k} value={k}>
                {KIND_LABEL[k]}
              </option>
            ))}
          </select>
        </Field>
        {(['employer_name', 'employer_address', 'employer_email', 'position'] as const).map((k) => (
          <Field key={k} name={k} missing={missing.has(k)}>
            <input
              {...inputProps(k)}
              type={k === 'employer_email' ? 'email' : 'text'}
              value={d[k] ?? ''}
              onChange={(e) => set(k, e.target.value || null)}
            />
          </Field>
        ))}
        {d.kind !== 'mandate' && d.kind !== 'jdg' && (
          <Field name="fte" missing={missing.has('fte')}>
            <input
              {...inputProps('fte')}
              type="number"
              min="0"
              max="10"
              step="0.01"
              inputMode="decimal"
              value={d.fte ?? ''}
              onChange={(e) => set('fte', toNumber(e.target.value))}
            />
          </Field>
        )}
        <Field name="gross_monthly" missing={missing.has('gross_monthly')}>
          <input
            {...inputProps('gross_monthly')}
            type="number"
            min="0"
            step="0.01"
            inputMode="decimal"
            value={d.gross_monthly ?? ''}
            onChange={(e) => set('gross_monthly', toNumber(e.target.value))}
          />
        </Field>
        <Field name="start_date" missing={missing.has('start_date')}>
          <input
            {...inputProps('start_date')}
            type="date"
            onClick={(e) => openNativePicker(e.currentTarget)}
            value={d.start_date ?? ''}
            onChange={(e) => set('start_date', e.target.value || null)}
          />
        </Field>
        {d.kind !== 'jdg' && (
          <Field name="indefinite" missing={missing.has('indefinite')}>
            <select
              {...inputProps('indefinite')}
              value={d.indefinite === null ? '' : d.indefinite ? 'yes' : 'no'}
              onChange={(e) => set('indefinite', e.target.value === '' ? null : e.target.value === 'yes')}
            >
              <option value="">Wybierz</option>
              <option value="yes">Tak, na czas nieokreślony</option>
              <option value="no">Nie, na czas określony</option>
            </select>
          </Field>
        )}
        {d.indefinite === false && (
          <Field name="end_date" missing={missing.has('end_date')}>
            <input
              {...inputProps('end_date')}
              type="date"
            onClick={(e) => openNativePicker(e.currentTarget)}
              value={d.end_date ?? ''}
              onChange={(e) => set('end_date', e.target.value || null)}
            />
          </Field>
        )}
        {d.kind === 'mandate' && (
          <Field name="voluntary_sickness" missing={missing.has('voluntary_sickness')}>
            <select
              {...inputProps('voluntary_sickness')}
              value={d.voluntary_sickness === null ? '' : d.voluntary_sickness ? 'yes' : 'no'}
              onChange={(e) =>
                set('voluntary_sickness', e.target.value === '' ? null : e.target.value === 'yes')
              }
            >
              <option value="">Nie wiem</option>
              <option value="yes">Tak, opłacam</option>
              <option value="no">Nie</option>
            </select>
          </Field>
        )}
      </div>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      <div className="row">
        <button className="btn" type="submit" disabled={busy}>
          {busy ? 'Zapisuję…' : 'Zatwierdź'}
        </button>
        {onCancel && (
          <button className="btn btn-secondary" type="button" onClick={onCancel}>
            Anuluj
          </button>
        )}
      </div>
    </form>
  )
}

export default ContractReview
