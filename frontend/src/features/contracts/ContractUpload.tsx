import { useId, useState } from 'react'
import type { FormEvent } from 'react'
import { api, ApiError } from '../../lib/api'
import type { ScanResult } from './types'

export const MAX_BYTES = 5 * 1024 * 1024
const ACCEPT = '.pdf,.png,.jpg,.jpeg,.txt,application/pdf,image/png,image/jpeg,text/plain'

/** Wgranie jednej umowy do odczytu przez AI. Zwraca szkic do przejrzenia (nic nie trafia jeszcze do profilu). */
export function ContractUpload({ onScanned }: { onScanned: (r: ScanResult) => void }) {
  const inputId = useId()
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!file) return
    if (file.size > MAX_BYTES) {
      setError('Plik jest za duży (maksymalnie 5 MB).')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const result = await api<ScanResult>('/api/contracts/scan', { method: 'POST', body: form })
      onScanned(result)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Nie udało się odczytać umowy.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card stack" onSubmit={submit} aria-label="Dodaj umowę">
      <h2>Dodaj umowę</h2>
      <p className="muted">
        Wgraj umowę o pracę, zlecenie albo umowę B2B (PDF, zdjęcie lub tekst, do 5 MB). Asystent AI
        odczyta dane, a Ty je sprawdzisz, zanim cokolwiek zapiszemy. Możesz dodać kilka umów, np.
        etat i zlecenie.
      </p>
      <div className="field">
        <label htmlFor={inputId}>Plik z umową</label>
        <input
          id={inputId}
          type="file"
          accept={ACCEPT}
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null)
            setError(null)
          }}
        />
      </div>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      <div className="row">
        <button className="btn" type="submit" disabled={!file || busy}>
          {busy ? 'Czytam umowę…' : 'Odczytaj umowę'}
        </button>
        <span className="badge-sim">AI</span>
      </div>
    </form>
  )
}

export default ContractUpload
