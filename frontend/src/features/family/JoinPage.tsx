import { useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import { isOnboarded } from '../../lib/onboarding'
import { useSession } from '../../lib/session'
import { Button } from '../../ui/Button'
import { Icon } from '../../ui/Icon'
import { Progress } from '../../ui/controls'
import '../../ui/ui.css'
import '../onboarding/flow.css'

const CODE_LEN = 8

export default function JoinPage() {
  const { refresh, family, user } = useSession()
  const navigate = useNavigate()
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [focused, setFocused] = useState(false)
  const input = useRef<HTMLInputElement>(null)

  // po dołączeniu do rodziny pokazujemy dalszą część onboardingu (dzieci, partner, umowy, poczta)
  if (family) return isOnboarded(user?.id) ? <Navigate to="/" replace /> : <Navigate to="/start" replace state={{ step: 'children' }} />

  async function submit(e?: FormEvent) {
    e?.preventDefault()
    if (!code.trim() || busy) return
    setBusy(true)
    setError(null)
    try {
      await api('/api/families/join', { method: 'POST', body: { code: code.trim() } })
      setSent(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Nie udało się wysłać prośby.')
    } finally {
      setBusy(false)
    }
  }

  async function checkStatus() {
    setBusy(true)
    await refresh()
    setBusy(false)
    setError('Prośba jeszcze czeka na akceptację. Spróbuj za chwilę.')
  }

  if (sent) {
    return (
      <div className="flow flow-pink">
        <div className="flow-body flow-center">
          <div className="flow-art" style={{ color: 'var(--pink)' }}>
            <Icon name="checkCircle" size={44} />
          </div>
          <h1 className="flow-title">Prośba wysłana</h1>
          <p className="flow-lead" role="status">
            Drugi rodzic zobaczy ją po zalogowaniu i może ją zaakceptować. Wtedy od razu zobaczysz Waszą rodzinę.
          </p>
          {error && <p className="flow-lead">{error}</p>}
        </div>
        <div className="flow-foot">
          <Button variant="white" block icon="refresh" disabled={busy} onClick={() => void checkStatus()}>
            Sprawdź status
          </Button>
        </div>
      </div>
    )
  }

  const boxes = Array.from({ length: Math.max(CODE_LEN, code.length) }, (_, i) => code[i] ?? '')

  return (
    <div className="flow">
      <div className="flow-top">
        <button type="button" className="icon-btn icon-btn-solid" aria-label="Wróć" onClick={() => navigate('/start')}>
          <Icon name="arrowLeft" size={20} />
        </button>
        <Progress value={0.4} label="Dołączanie do rodziny" />
      </div>
      <form className="flow-body" onSubmit={submit}>
        <div className="flow-art rise">
          <Icon name="link" size={40} />
        </div>
        <h1 className="flow-title rise" style={{ ['--i' as string]: 1 }}>
          Wpisz kod zaproszenia
        </h1>
        <p className="flow-lead rise" style={{ ['--i' as string]: 2 }}>
          Drugi rodzic znajdzie go w aplikacji, w zakładce Rodzina.
        </p>
        <label className="code-input-wrap rise" style={{ ['--i' as string]: 3 }} onClick={() => input.current?.focus()}>
          <span className="sr-only">Kod zaproszenia</span>
          <input
            ref={input}
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 16))}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            maxLength={16}
            aria-label="Kod zaproszenia"
          />
          <span className="code-boxes" aria-hidden="true">
            {boxes.map((ch, i) => (
              <span key={i} className={`code-box ${focused && i === Math.min(code.length, boxes.length - 1) ? 'is-active' : ''}`}>
                {ch}
              </span>
            ))}
          </span>
        </label>
        {error && (
          <p role="alert" className="alert">
            <Icon name="alert" size={20} />
            {error}
          </p>
        )}
      </form>
      <div className="flow-foot">
        <Button block icon="arrowRight" disabled={busy || !code.trim()} onClick={() => void submit()}>
          {busy ? 'Wysyłam…' : 'Wyślij prośbę'}
        </Button>
      </div>
    </div>
  )
}
