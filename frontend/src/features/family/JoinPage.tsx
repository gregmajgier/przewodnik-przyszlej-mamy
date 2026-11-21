import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import { useSession } from '../../lib/session'

export default function JoinPage() {
  const { refresh, family } = useSession()
  const navigate = useNavigate()
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api('/api/families/join', { method: 'POST', body: { code } })
      setSent(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Nie udało się wysłać prośby.')
    } finally {
      setBusy(false)
    }
  }

  async function checkStatus() {
    await refresh()
    navigate('/rodzina')
  }

  if (family) {
    return (
      <div className="card stack">
        <h1>Dołącz do rodziny</h1>
        <p>Należysz już do rodziny.</p>
        <Link to="/rodzina">Przejdź do rodziny</Link>
      </div>
    )
  }

  if (sent) {
    return (
      <div className="card stack">
        <h1>Prośba wysłana</h1>
        <p role="status">
          Czekaj na akceptację. Założyciel rodziny zobaczy Twoją prośbę po zalogowaniu i może ją
          zaakceptować.
        </p>
        <div className="row">
          <button type="button" className="btn" onClick={checkStatus}>
            Sprawdź status
          </button>
        </div>
      </div>
    )
  }

  return (
    <form className="card stack" onSubmit={submit} style={{ maxWidth: '32rem' }}>
      <h1>Dołącz do rodziny</h1>
      <p className="muted">
        Poproś drugiego rodzica o kod zaproszenia (ma go w zakładce „Rodzina”) i wpisz go poniżej.
      </p>
      <label className="field">
        Kod zaproszenia
        <input
          value={code}
          onChange={(e) => setCode(e.target.value)}
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          maxLength={16}
        />
      </label>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      <div className="row">
        <button type="submit" className="btn" disabled={busy || !code.trim()}>
          Wyślij prośbę
        </button>
        <Link to="/start">Wróć</Link>
      </div>
    </form>
  )
}
