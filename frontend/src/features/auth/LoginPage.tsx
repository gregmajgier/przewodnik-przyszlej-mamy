import { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { Doodles } from '../../brand/Doodles'
import { BrandMark, Wordmark } from '../../brand/Splash'
import { Logo } from '../../components/Logo'
import { api } from '../../lib/api'
import { useSession } from '../../lib/session'
import { isOnboarded } from '../../lib/onboarding'
import type { Persona } from '../../lib/types'
import { Button } from '../../ui/Button'
import { Icon } from '../../ui/Icon'
import { Avatar, Progress } from '../../ui/controls'
import '../../brand/brand.css'
import '../../ui/ui.css'
import '../onboarding/flow.css'

type Step = 'welcome' | 'method' | 'account' | 'connecting'

const CONNECT_STEPS = ['Potwierdzam tożsamość', 'Pobieram dane z ZUS', 'Szukam Waszej rodziny']
const CONNECT_STEP_MS = 650

function Welcome({ onNext }: { onNext: () => void }) {
  return (
    <div className="flow flow-pink">
      <Doodles set="welcome" opacity={0.75} />
      <div className="flow-top">
        <Wordmark light />
      </div>
      <div className="flow-body flow-center">
        <div className="welcome-copy rise">
          <p>Mamo! Tato! Masz wiele na głowie…</p>
          <p>
            <span className="wordmark">
              <Logo className="wordmark-logo" color="#fff" duration={1400} />
              <span>Rodzina</span>
            </span>
            pomoże.
          </p>
        </div>
        <div className="welcome-points rise" style={{ ['--i' as string]: 3 }}>
          <span>
            <Icon name="coins" size={18} /> Świadczenia
          </span>
          <span>
            <Icon name="docCheck" size={18} /> Wnioski
          </span>
          <span>
            <Icon name="calendar" size={18} /> Terminy
          </span>
        </div>
      </div>
      <div className="flow-foot rise" style={{ ['--i' as string]: 5 }}>
        <Button variant="white" block icon="arrowRight" onClick={onNext}>
          Zaczynamy
        </Button>
        <button type="button" className="flow-skip" onClick={onNext}>
          Mam już konto
        </button>
      </div>
    </div>
  )
}

export default function LoginPage() {
  const { user, family, login } = useSession()
  const navigate = useNavigate()
  const [step, setStep] = useState<Step>('welcome')
  const [personas, setPersonas] = useState<Persona[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (step !== 'account' || personas) return
    let cancelled = false
    api<Persona[]>('/api/auth/personas')
      .then((p) => !cancelled && setPersonas(p))
      .catch(() => !cancelled && setError('Nie udało się połączyć z mObywatelem. Spróbuj ponownie za chwilę.'))
    return () => {
      cancelled = true
    }
  }, [step, personas])

  useEffect(() => {
    if (step !== 'connecting' || tick >= CONNECT_STEPS.length) return
    const t = window.setTimeout(() => setTick((n) => n + 1), CONNECT_STEP_MS)
    return () => window.clearTimeout(t)
  }, [step, tick])

  if (user && step !== 'connecting') {
    return (
      <Navigate
        to={user.role === 'official' ? '/urzednik' : family && isOnboarded(user.id) ? '/' : '/start'}
        replace
      />
    )
  }

  async function choose(persona: Persona) {
    setError(null)
    setTick(0)
    setStep('connecting')
    const started = Date.now()
    try {
      const { user: me, family: fam } = await login(persona.id)
      const wait = Math.max(0, CONNECT_STEPS.length * CONNECT_STEP_MS + 300 - (Date.now() - started))
      window.setTimeout(() => navigate(fam && isOnboarded(me.id) ? '/' : '/start', { replace: true }), import.meta.env.MODE === 'test' ? 0 : wait)
    } catch {
      setError('Nie udało się zalogować. Spróbuj ponownie.')
      setStep('account')
    }
  }

  if (step === 'welcome') return <Welcome onNext={() => setStep('method')} />

  if (step === 'connecting') {
    return (
      <div className="flow flow-pink">
        <div className="flow-body flow-center">
          <BrandMark duration={1200} />
          <h1 className="flow-title" style={{ marginTop: '1.5rem' }}>
            Łączę z mObywatelem
          </h1>
          <ol className="connect-steps" aria-live="polite">
            {CONNECT_STEPS.slice(0, tick + 1).map((s, i) => {
              const done = i < tick
              return (
                <li key={s} className={done ? 'is-done' : ''}>
                  <span className="connect-mark" aria-hidden="true">
                    {done ? <Icon name="check" size={18} stroke={2.4} /> : <Icon name="refresh" size={18} className="spin" />}
                  </span>
                  {s}
                  <span className="sr-only">{done ? ' — gotowe' : ' — w toku'}</span>
                </li>
              )
            })}
          </ol>
        </div>
      </div>
    )
  }

  return (
    <div className="flow">
      <div className="flow-top">
        <button
          type="button"
          className="icon-btn icon-btn-solid"
          aria-label="Wróć"
          onClick={() => setStep(step === 'account' ? 'method' : 'welcome')}
        >
          <Icon name="arrowLeft" size={20} />
        </button>
        <Progress value={step === 'method' ? 0.33 : 0.66} label="Logowanie" />
      </div>

      {step === 'method' && (
        <>
          <div className="flow-body">
            <div className="flow-art rise">
              <Icon name="shield" size={40} />
            </div>
            <h1 className="flow-title rise" style={{ ['--i' as string]: 1 }}>
              Zaloguj się bezpiecznie
            </h1>
            <p className="flow-lead rise" style={{ ['--i' as string]: 2 }}>
              Potwierdzimy Twoją tożsamość przez mObywatel. Nie zakładasz konta i nie pamiętasz żadnego hasła — dane z ZUS
              pobierzemy za Ciebie.
            </p>
            <div className="flow-note rise" style={{ ['--i' as string]: 3 }}>
              <Icon name="lock" size={18} />
              <span>Widzimy tylko to, co potrzebne do świadczeń i wniosków. Możesz to w każdej chwili wycofać.</span>
            </div>
          </div>
          <div className="flow-foot">
            <Button variant="dark" block leading="shield" onClick={() => setStep('account')}>
              Zaloguj przez mObywatel
            </Button>
            <Link className="flow-skip" to="/urzednik/logowanie">
              Jestem urzędnikiem gminy
            </Link>
          </div>
        </>
      )}

      {step === 'account' && (
        <div className="flow-body">
          <h1 className="flow-title rise">Wybierz profil</h1>
          <p className="flow-lead rise" style={{ ['--i' as string]: 1 }}>
            mObywatel znalazł te profile na Twoim urządzeniu.
          </p>
          {error && (
            <p role="alert" className="alert" style={{ marginBottom: '1rem' }}>
              <Icon name="alert" size={20} />
              {error}
            </p>
          )}
          <div className="card idp rise" style={{ ['--i' as string]: 2 }}>
            <div className="idp-head">
              <Icon name="shield" size={20} />
              mObywatel
            </div>
            {!personas && !error && (
              <div style={{ padding: '1.25rem' }}>
                <p role="status" className="sr-only">
                  Ładowanie profili…
                </p>
                <div className="skeleton" style={{ height: '3.5rem', marginBottom: '0.75rem' }} />
                <div className="skeleton" style={{ height: '3.5rem' }} />
              </div>
            )}
            <ul className="list">
              {personas?.map((p, i) => (
                <li key={p.id}>
                  <button type="button" className="list-row" onClick={() => void choose(p)}>
                    <Avatar name={p.name} tone={i % 2 ? 'sky' : 'peach'} size={48} />
                    <span className="list-row-main">
                      <span className="list-row-title">{p.name}</span>
                      <span className="list-row-sub">{p.role_label}</span>
                    </span>
                    <span className="list-row-end">
                      <Icon name="chevronRight" size={20} />
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}
