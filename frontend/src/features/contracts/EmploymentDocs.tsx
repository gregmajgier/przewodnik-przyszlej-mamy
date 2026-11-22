import { useEffect, useState } from 'react'
import { ApiError } from '../../lib/api'
import { describeDocument, importDocument, listDocuments, openDocumentPdf } from './documents'
import type { EmploymentDocument } from './types'

/** Umowy z e-teczki pracodawcy, których rodzic jeszcze nie dodał (strona /umowy). */
export default function EmploymentDocs({ version, onAdded }: { version: number; onAdded: () => void }) {
  const [docs, setDocs] = useState<EmploymentDocument[] | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    listDocuments()
      .then((list) => !cancelled && setDocs(list))
      .catch(() => !cancelled && setDocs([]))
    return () => {
      cancelled = true
    }
  }, [version])

  const pending = (docs ?? []).filter((d) => !d.contract_id)
  if (pending.length === 0) return null

  async function add(id: string) {
    setBusy(id)
    setError(null)
    try {
      const c = await importDocument(id)
      setDocs((prev) => prev?.map((d) => (d.id === id ? { ...d, contract_id: c.id } : d)) ?? prev)
      onAdded()
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Nie udało się dodać umowy.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="card stack" aria-labelledby="employer-docs-h">
      <h2 id="employer-docs-h">Umowy z e-teczki pracodawcy</h2>
      <p className="muted">Te umowy czekają na dodanie. Wystarczy jedno kliknięcie, a dane wypełnią się same.</p>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      <ul className="contract-list stack">
        {pending.map((d) => (
          <li key={d.id} className="row" style={{ justifyContent: 'space-between', flexWrap: 'wrap' }}>
            <div>
              <strong>{d.title}</strong>
              <br />
              <span className="muted">{describeDocument(d)}</span>
            </div>
            <div className="row">
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() =>
                  void openDocumentPdf(d.id).catch((e) =>
                    setError(e instanceof ApiError ? e.detail : 'Nie udało się otworzyć umowy.'),
                  )
                }
              >
                Podgląd PDF
              </button>
              <button type="button" className="btn" disabled={busy !== null} onClick={() => void add(d.id)}>
                {busy === d.id ? 'Dodaję…' : 'Dodaj'}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
