import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { Ribbons } from '../../brand/Ribbons'
import { Wordmark } from '../../brand/Splash'
import { ApiError } from '../../lib/api'
import { useSession } from '../../lib/session'
import { Button } from '../../ui/Button'
import { Icon } from '../../ui/Icon'
import type { IconName } from '../../ui/Icon'
import '../../brand/brand.css'
import '../../ui/ui.css'
import './official.css'

const PERKS: { icon: IconName; text: string }[] = [
  { icon: 'doc', text: 'Wklejasz uchwałę, a formularz świadczenia wypełnia się sam' },
  { icon: 'checkCircle', text: 'Zatwierdzasz warunki, które sprawdzimy u każdej rodziny' },
  { icon: 'family', text: 'Po publikacji rodzice z Twojego obszaru od razu je widzą' },
]

// Konta z danych startowych (backend/app/seed/officials.py) — wejście jednym kliknięciem do pokazu panelu.
const DEMO_ACCOUNTS = [
  { email: 'urzednik.krakow@mrodzina.local', password: 'demo1234', unit: 'Gmina Miejska Kraków', icon: 'pin' as IconName },
  { email: 'urzednik.malopolska@mrodzina.local', password: 'demo1234', unit: 'Województwo Małopolskie', icon: 'globe' as IconName },
]

export default function OfficialLogin() {
  const { user, loginOfficial } = useSession()
  const navigate = useNavigate()
  // pokaz: formularz od razu wypełniony kontem testowym gminy — wystarczy kliknąć „Zaloguj się”
  const [email, setEmail] = useState(DEMO_ACCOUNTS[0].email)
  const [password, setPassword] = useState(DEMO_ACCOUNTS[0].password)
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (user?.role === 'official') return <Navigate to="/urzednik" replace />

  async function submit(e: FormEvent) {
    e.preventDefault()
    await signIn(email.trim(), password)
  }

  async function signIn(login: string, pass: string) {
    setBusy(true)
    setError(null)
    try {
      const u = await loginOfficial(login, pass)
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
    <div className="off-login">
      <section className="off-login-hero" aria-labelledby="off-login-h">
        <Ribbons />
        <div className="off-login-hero-inner">
          <Wordmark light className="off-login-mark" />
          <p className="off-login-tag">Panel samorządu</p>
          <h1 id="off-login-h">Świadczenia Twojej gminy tam, gdzie szukają ich rodzice.</h1>
          <ul className="off-login-perks">
            {PERKS.map((p, i) => (
              <li key={p.icon} className="rise" style={{ ['--i' as string]: i + 2 }}>
                <span className="off-login-perk-icon">
                  <Icon name={p.icon} size={20} />
                </span>
                {p.text}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="off-login-side">
        <form className="off-login-card rise" onSubmit={submit} aria-label="Logowanie urzędnika">
          <span className="icon-tile tone-lilac" aria-hidden="true">
            <Icon name="shield" size={24} />
          </span>
          <div>
            <h2>Zaloguj się</h2>
            <p className="muted">Konto służbowe nadaje zespół mRodziny: jedno na gminę, powiat albo województwo.</p>
          </div>
          <div className="field">
            <label htmlFor="official-email">E-mail służbowy</label>
            <input
              id="official-email"
              type="email"
              autoComplete="username"
              placeholder="imie.nazwisko@urzad.gov.pl"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="official-password">Hasło</label>
            <div className="off-input-wrap">
              <input
                id="official-password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button
                type="button"
                className="off-input-btn"
                aria-label={showPassword ? 'Ukryj hasło' : 'Pokaż hasło'}
                aria-pressed={showPassword}
                onClick={() => setShowPassword((v) => !v)}
              >
                <Icon name="eye" size={20} />
              </button>
            </div>
          </div>
          {error && (
            <p role="alert" className="alert">
              <Icon name="alert" size={18} /> {error}
            </p>
          )}
          <Button type="submit" block disabled={busy} icon={busy ? undefined : 'arrowRight'}>
            {busy ? 'Loguję…' : 'Zaloguj się'}
          </Button>
          <p className="off-login-foot">
            <Icon name="lock" size={16} /> Połączenie szyfrowane. Sesja wygasa po 12 godzinach.
          </p>
        </form>
        <section className="off-demo rise" style={{ ['--i' as string]: 1 }} aria-labelledby="off-demo-h">
          <h2 id="off-demo-h">Konta testowe</h2>
          <p className="muted small">Wejdź jednym kliknięciem i zobacz panel od środka.</p>
          {DEMO_ACCOUNTS.map((a) => (
            <button
              key={a.email}
              type="button"
              className="off-demo-btn"
              disabled={busy}
              onClick={() => {
                setEmail(a.email)
                setPassword(a.password)
                void signIn(a.email, a.password)
              }}
            >
              <span className="icon-tile tone-lilac" aria-hidden="true">
                <Icon name={a.icon} size={20} />
              </span>
              <span className="off-demo-text">
                <strong>{a.unit}</strong>
                <span>{a.email}</span>
              </span>
              <Icon name="arrowRight" size={18} />
            </button>
          ))}
        </section>
        <Link to="/logowanie" className="off-login-parent">
          Jesteś rodzicem? <strong>Wejdź przez mObywatel</strong>
        </Link>
      </section>
    </div>
  )
}
