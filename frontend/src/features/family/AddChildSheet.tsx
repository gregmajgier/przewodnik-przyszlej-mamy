import { useState } from 'react'
import type { FormEvent } from 'react'
import { api, ApiError } from '../../lib/api'
import { Button } from '../../ui/Button'
import { DateField, Segmented } from '../../ui/controls'
import { Sheet } from '../../ui/Sheet'

/** Arkusz „Dodaj dziecko”: imię, urodzone / w drodze, data. Zapisuje w rodzinie i woła `onAdded`. */
export function AddChildSheet({ open, onClose, onAdded }: { open: boolean; onClose: () => void; onAdded: () => void | Promise<void> }) {
  const [name, setName] = useState('')
  const [kind, setKind] = useState<'born' | 'expected'>('born')
  const [date, setDate] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e?: FormEvent) {
    e?.preventDefault()
    if (!name.trim() || !date || busy) return
    setBusy(true)
    setError(null)
    try {
      await api('/api/families/me/children', {
        method: 'POST',
        body: {
          name: name.trim(),
          birth_date: kind === 'born' ? date : null,
          due_date: kind === 'expected' ? date : null,
        },
      })
      setName('')
      setDate('')
      await onAdded()
      onClose()
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Nie udało się dodać dziecka.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Sheet
      open={open}
      onClose={onClose}
      busy={busy}
      title="Dodaj dziecko"
      subtitle="Na podstawie wieku podpowiemy, co mu przysługuje."
      footer={
        <Button block disabled={!name.trim() || !date || busy} onClick={() => void submit()}>
          {busy ? 'Zapisuję…' : 'Dodaj dziecko'}
        </Button>
      }
    >
      <form className="stack" onSubmit={submit}>
        <Segmented
          label="Dziecko"
          value={kind}
          onChange={setKind}
          options={[
            { value: 'born', label: 'Już jest z nami' },
            { value: 'expected', label: 'W drodze' },
          ]}
        />
        <label className="field">
          Imię
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="np. Zosia" autoComplete="off" />
        </label>
        <DateField
          label={kind === 'born' ? 'Data urodzenia' : 'Przewidywany termin porodu'}
          value={date}
          onChange={setDate}
        />
        {error && (
          <p role="alert" className="alert">
            {error}
          </p>
        )}
        <button type="submit" hidden />
      </form>
    </Sheet>
  )
}
