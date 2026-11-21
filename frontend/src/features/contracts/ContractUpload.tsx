import { useId, useState } from 'react'
import type { ChangeEvent } from 'react'
import { api, ApiError } from '../../lib/api'
import './contracts.css'
import { ACCEPTED_TYPES, MAX_FILE_BYTES, MAX_FILES } from './types'
import type { ScanResult } from './types'

interface Props {
  /** Ile umów można jeszcze dodać (limit 5 na rodzica). */
  slotsLeft?: number
  onScanned: (result: ScanResult) => void
}

/** Wgrywanie jednej lub kilku umów; każdy plik jest skanowany osobno (po kolei). */
export default function ContractUpload({ slotsLeft = MAX_FILES, onScanned }: Props) {
  const inputId = useId()
  const [busy, setBusy] = useState(false)
  const [errors, setErrors] = useState<string[]>([])

  async function onChange(e: ChangeEvent<HTMLInputElement>) {
    const input = e.target
    const files = Array.from(input.files ?? [])
    input.value = ''
    if (files.length === 0) return
    const problems: string[] = []
    let queue = files
    if (files.length > slotsLeft) {
      problems.push(`Możesz dodać jeszcze ${slotsLeft} ${slotsLeft === 1 ? 'umowę' : 'umowy'} — resztę pominęliśmy.`)
      queue = files.slice(0, Math.max(slotsLeft, 0))
    }
    setBusy(true)
    setErrors([])
    for (const file of queue) {
      if (file.size > MAX_FILE_BYTES) {
        problems.push(`${file.name}: plik jest za duży (maksymalnie 5 MB).`)
        continue
      }
      try {
        const body = new FormData()
        body.append('file', file)
        onScanned(await api<ScanResult>('/api/contracts/scan', { method: 'POST', body }))
      } catch (err) {
        problems.push(`${file.name}: ${err instanceof ApiError ? err.detail : 'nie udało się wysłać pliku.'}`)
        if (err instanceof ApiError && (err.status === 429 || err.status === 503)) break // limit/awaria — dalsze próby nie mają sensu
      }
    }
    setErrors(problems)
    setBusy(false)
  }

  return (
    <div className="dropzone">
      <label htmlFor={inputId}>
        <strong>Wybierz umowy</strong>
      </label>
      <input
        id={inputId}
        type="file"
        multiple
        accept={ACCEPTED_TYPES}
        onChange={onChange}
        disabled={busy || slotsLeft <= 0}
      />
      <p className="muted" style={{ margin: 0 }}>
        PDF z tekstem, zdjęcie (PNG, JPG) albo plik tekstowy, do 5 MB. Przeczytamy je za Ciebie — a Ty
        sprawdzisz, co znaleźliśmy, zanim cokolwiek zapiszemy.
      </p>
      {busy && <p role="status">Czytam umowę…</p>}
      {slotsLeft <= 0 && <p className="muted">Masz już 5 umów — usuń jedną, żeby dodać kolejną.</p>}
      {errors.map((m) => (
        <p key={m} role="alert" className="alert">
          {m}
        </p>
      ))}
    </div>
  )
}
