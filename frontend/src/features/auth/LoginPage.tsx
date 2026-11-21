import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Logo } from '../../components/Logo'
import { api } from '../../lib/api'
import { useSession } from '../../lib/session'
import type { Persona } from '../../lib/types'

export default function LoginPage() {
  const { login } = useSession()
  const navigate = useNavigate()
  const [personas, setPersonas] = useState<Persona[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    api<Persona[]>('/api/auth/personas')
      .then((p) => !cancelled && setPersonas(p))
      .catch(() => !cancelled && setError('Nie udało się pobrać listy kont. Spróbuj ponownie za chwilę.'))
    return () => {
      cancelled = true
    }
  }, [])

  async function choose(persona: Persona) {
    setBusy(true)
    setError(null)
    try {
      const { family } = await login(persona.id)
      navigate(family ? '/' : '/start', { replace: true })
    } catch {
      setError('Nie udało się zalogować. Spróbuj ponownie.')
      setBusy(false)
    }
  }

  return (
    <main className="shell-main stack" style={{ maxWidth: '40rem' }}>
      <div className="row">
        <Logo className="logo-mark" animate={false} />
        <span className="wordmark">Rodzina</span>
      </div>
      <h1>Zaloguj się przez mObywatela</h1>
      <p className="muted">
        <span className="badge-sim">symulacja</span> To prototyp: wybierz osobę, a dane z ZUS i
        mObywatela pobierzemy za Ciebie.
      </p>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {!personas && !error && <p role="status">Ładowanie…</p>}
      <ul className="stack" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {personas?.map((p) => (
          <li key={p.id}>
            <button
              type="button"
              className="card persona-card"
              disabled={busy}
              onClick={() => choose(p)}
            >
              <strong>{p.name}</strong>
              <br />
              <span className="muted">{p.role_label}</span>
            </button>
          </li>
        ))}
      </ul>
    </main>
  )
}
