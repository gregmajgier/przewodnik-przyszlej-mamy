import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import { describeChild } from '../../lib/format'
import { useSession } from '../../lib/session'
import type { KnownChild, ParentProfile } from '../../lib/types'

type Step = 'family' | 'children' | 'parent'

function ChildrenStep({ onDone }: { onDone: () => void }) {
  const { family, refresh } = useSession()
  const [known, setKnown] = useState<KnownChild[] | null>(null)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    api<ParentProfile>('/api/profile/me')
      .then((p) => {
        if (cancelled) return
        const existing = new Set((family?.children ?? []).map((c) => c.name))
        const fresh = p.known_children.filter((k) => !existing.has(k.name))
        if (fresh.length === 0) {
          onDone()
          return
        }
        setKnown(fresh)
        setSelected(new Set(fresh.map((_, i) => i)))
      })
      .catch(() => !cancelled && onDone()) // brak danych z ZUS: można dodać dzieci później w „Rodzina”
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function toggle(i: number) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(i)) next.delete(i)
      else next.add(i)
      return next
    })
  }

  async function approve() {
    if (!known) return
    setBusy(true)
    setError(null)
    try {
      for (const [i, k] of known.entries()) {
        if (!selected.has(i)) continue
        await api('/api/families/me/children', {
          method: 'POST',
          body: { name: k.name, birth_date: k.birth_date, due_date: k.due_date },
        })
      }
      await refresh()
      onDone()
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Nie udało się zapisać dzieci.')
      setBusy(false)
    }
  }

  if (!known) return <p role="status">Ładowanie…</p>

  return (
    <section className="card stack" aria-labelledby="kids-h">
      <h2 id="kids-h">Dzieci w rodzinie</h2>
      <p className="muted">
        Znamy już te dzieci z danych ZUS. Zaznacz te, które mają trafić do Waszej rodziny — resztę
        możesz dodać później.
      </p>
      <ul style={{ listStyle: 'none', padding: 0 }} className="stack">
        {known.map((k, i) => (
          <li key={`${k.name}-${i}`}>
            <label className="row">
              <input type="checkbox" checked={selected.has(i)} onChange={() => toggle(i)} />
              <span>
                {k.name} <span className="muted">— {describeChild({ status: k.due_date && !k.birth_date ? 'expected' : 'born', birth_date: k.birth_date, due_date: k.due_date })}</span>
              </span>
            </label>
          </li>
        ))}
      </ul>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      <div className="row">
        <button type="button" className="btn" disabled={busy} onClick={approve}>
          Zatwierdź dzieci
        </button>
        <button type="button" className="btn btn-secondary" disabled={busy} onClick={onDone}>
          Pomiń
        </button>
      </div>
    </section>
  )
}

export default function OnboardingPage() {
  const { family, refresh } = useSession()
  const navigate = useNavigate()
  const [step, setStep] = useState<Step>(family ? 'children' : 'family')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function createFamily() {
    setBusy(true)
    setError(null)
    try {
      await api('/api/families', { method: 'POST', body: {} })
      await refresh()
      setStep('children')
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Nie udało się założyć rodziny.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack" style={{ maxWidth: '40rem' }}>
      <h1>Zaczynamy</h1>

      {step === 'family' && (
        <section className="card stack" aria-labelledby="fam-h">
          <h2 id="fam-h">Twoja rodzina</h2>
          <p className="muted">
            Załóż rodzinę — wszystkie dane (Twoje, drugiego rodzica i dzieci) będą w jednym miejscu.
          </p>
          {error && (
            <p role="alert" className="alert">
              {error}
            </p>
          )}
          <div className="row">
            <button type="button" className="btn" disabled={busy} onClick={createFamily}>
              Załóż rodzinę
            </button>
            <Link to="/dolacz">Dołącz do rodziny</Link>
          </div>
        </section>
      )}

      {step === 'children' && <ChildrenStep onDone={() => setStep('parent')} />}

      {step === 'parent' && (
        <section className="card stack" aria-labelledby="par-h">
          <h2 id="par-h">Drugi rodzic</h2>
          {family?.family.invite_code ? (
            <>
              <p className="muted">
                Przekaż ten kod drugiemu rodzicowi. Wpisze go po zalogowaniu w „Dołącz do rodziny”, a Ty
                zaakceptujesz prośbę.
              </p>
              <p className="invite-code" aria-label="Kod zaproszenia">
                {family.family.invite_code}
              </p>
            </>
          ) : (
            <p className="muted">Kod zaproszenia znajdziesz w zakładce „Rodzina”.</p>
          )}
          <div className="row">
            <button type="button" className="btn" onClick={() => navigate('/analiza')}>
              Gotowe, przejdź dalej
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => navigate('/analiza')}>
              Wychowuję dziecko samodzielnie
            </button>
          </div>
        </section>
      )}
    </div>
  )
}
