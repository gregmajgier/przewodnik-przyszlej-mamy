import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { Logo } from '../../components/Logo'
import { ApiError } from '../../lib/api'
import { useSession } from '../../lib/session'
import './official.css'

export default function OfficialLogin() {
  const { user, loginOfficial } = useSession()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (user?.role === 'official') return <Navigate to="/urzednik" replace />

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const u = await loginOfficial(email.trim(), password)
      if (u.role !== 'official') {
        setError('To konto nie jest kontem urzędnika.')
        return
      }
      navigate('/urzednik', { replace: true })
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? 'Nieprawidłowy e-mail lub hasło.'
          : err instanceof ApiError
            ? err.detail
            : 'Nie udało się zalogować.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="official-main stack" style={{ maxWidth: '28rem' }}>
      <div className="row">
        <Logo className="logo-mark" animate={false} />
        <span className="wordmark">Rodzina</span>
      </div>
      <h1>Panel jednostki samorządu</h1>
      <p className="muted">
        Konta urzędników nadaje zespół mRodziny. Każde konto jest przypisane do jednej gminy, powiatu
        albo województwa.
      </p>
      <form className="card stack" onSubmit={submit} aria-label="Logowanie urzędnika">
        <div className="field">
          <label htmlFor="official-email">E-mail służbowy</label>
          <input
            id="official-email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="official-password">Hasło</label>
          <input
            id="official-password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        {error && (
          <p role="alert" className="alert">
            {error}
          </p>
        )}
        <button className="btn" type="submit" disabled={busy}>
          {busy ? 'Loguję…' : 'Zaloguj się'}
        </button>
      </form>
    </main>
  )
}
