import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import type { MailStatus } from './types'

export default function MailSettings() {
  const [status, setStatus] = useState<MailStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api<MailStatus>('/api/mail/status')
      .then((r) => !cancelled && setStatus(r))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.detail : 'Nie udało się pobrać ustawień.'))
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="stack">
      <p>
        <Link to="/poczta">← Poczta</Link>
      </p>
      <h1>Ustawienia poczty</h1>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {!status && !error && <p role="status">Ładowanie…</p>}
      {status && (
        <section className="card stack" aria-labelledby="mail-conn-h">
          <h2 id="mail-conn-h">
            {status.connected ? 'Gmail podłączony' : 'Poczta niepodłączona'}{' '}
            {status.simulated && <span className="badge-sim">SYMULACJA</span>}
          </h2>
          <p>
            Skrzynka: <strong>{status.address}</strong>
          </p>
          <h3>Co czytamy</h3>
          <p>{status.scope_note}</p>
          <p className="muted">
            W prototypie skrzynka jest symulowana: wysłane wnioski trafiają do „Wysłanych”, a odpowiedzi
            pracodawcy, ZUS i urzędu są przygotowanymi wiadomościami.
          </p>
        </section>
      )}
      <p className="notice">Wkrótce: przypomnienia mailem i SMS-em.</p>
    </div>
  )
}
