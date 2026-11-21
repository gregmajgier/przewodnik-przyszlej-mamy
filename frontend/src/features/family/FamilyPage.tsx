import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import { describeChild } from '../../lib/format'
import { useSession } from '../../lib/session'
import type { FamilyView } from '../../lib/types'
import { SituationMenu } from '../situations/SituationMenu'
import { useFamilyMode } from '../situations/useFamilyMode'

export default function FamilyPage() {
  const { user, refresh } = useSession()
  const familyMode = useFamilyMode()
  const [view, setView] = useState<FamilyView | null>(null)
  const [noFamily, setNoFamily] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [childName, setChildName] = useState('')
  const [childKind, setChildKind] = useState<'born' | 'expected'>('born')
  const [childDate, setChildDate] = useState('')

  const load = useCallback(async () => {
    try {
      setView(await api<FamilyView>('/api/families/me'))
      setNoFamily(false)
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setNoFamily(true)
      else setError(e instanceof ApiError ? e.detail : 'Nie udało się pobrać danych rodziny.')
    }
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load()
  }, [load])

  async function run(action: () => Promise<unknown>, alsoRefreshSession = false) {
    setError(null)
    try {
      await action()
      await load()
      if (alsoRefreshSession) await refresh()
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Nie udało się wykonać operacji.')
    }
  }

  const decide = (id: string, verb: 'accept' | 'reject') =>
    run(() => api(`/api/families/me/join-requests/${id}/${verb}`, { method: 'POST' }), true)

  async function addChild(e: FormEvent) {
    e.preventDefault()
    await run(async () => {
      await api('/api/families/me/children', {
        method: 'POST',
        body: {
          name: childName,
          birth_date: childKind === 'born' ? childDate : null,
          due_date: childKind === 'expected' ? childDate : null,
        },
      })
      setChildName('')
      setChildDate('')
    })
  }

  if (noFamily) {
    return (
      <div className="card stack">
        <h1>Rodzina</h1>
        <p>Nie należysz jeszcze do żadnej rodziny.</p>
        <div className="row">
          <Link className="btn" to="/start">
            Załóż rodzinę
          </Link>
          <Link to="/dolacz">Dołącz do rodziny</Link>
        </div>
      </div>
    )
  }
  if (!view) {
    return error ? (
      <p role="alert" className="alert">
        {error}
      </p>
    ) : (
      <p role="status">Ładowanie…</p>
    )
  }

  const isOwner = view.family.owner_id === user?.id

  return (
    <div className="stack">
      <h1>{view.family.name}</h1>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}

      {view.pending_requests.length > 0 && (
        <section className="card stack" aria-labelledby="req-h">
          <h2 id="req-h">Prośby o dołączenie</h2>
          {view.pending_requests.map((r) => (
            <div key={r.id} className="row">
              <span>{r.user_name} chce dołączyć do rodziny</span>
              <button type="button" className="btn" onClick={() => decide(r.id, 'accept')}>
                Akceptuj
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => decide(r.id, 'reject')}>
                Odrzuć
              </button>
            </div>
          ))}
        </section>
      )}

      <section className="card stack" aria-labelledby="members-h">
        <h2 id="members-h">Rodzice</h2>
        <ul>
          {view.members.map((m) => (
            <li key={m.id}>
              <span>{m.name}</span>
              {m.id === view.family.owner_id && <span className="muted"> (założyciel)</span>}
            </li>
          ))}
        </ul>
        {view.members.length < 2 && isOwner && view.family.invite_code && (
          <div className="stack">
            <p className="muted">Kod zaproszenia dla drugiego rodzica (ważny 7 dni):</p>
            <p className="invite-code" aria-label="Kod zaproszenia">
              {view.family.invite_code}
            </p>
            <div className="row">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => run(() => api('/api/families/me/invite-code', { method: 'POST' }))}
              >
                Wygeneruj nowy kod
              </button>
            </div>
          </div>
        )}
        {view.members.length >= 2 && (
          <p className="muted">Oboje rodzice widzą wszystkie dane rodziny.</p>
        )}
      </section>

      <section className="card stack" aria-labelledby="kids-h">
        <h2 id="kids-h">Dzieci</h2>
        {view.children.length === 0 && <p className="muted">Nie dodano jeszcze dzieci.</p>}
        <ul>
          {view.children.map((c) => (
            <li key={c.id}>
              <div className="row">
                <strong>{c.name}</strong>
                <span className="muted">{describeChild(c)}</span>
                <button
                  type="button"
                  className="btn btn-danger"
                  aria-label={`Usuń dziecko ${c.name}`}
                  onClick={() => run(() => api(`/api/families/me/children/${c.id}`, { method: 'DELETE' }))}
                >
                  Usuń
                </button>
              </div>
              {c.situation === 'loss' ? (
                <p className="muted sit-lost">Zmiana sytuacji została zapisana. Jesteśmy z Wami.</p>
              ) : (
                <>
                  <SituationMenu child={c} onChanged={load} />
                  <label className="sit-flag">
                    <input
                      type="checkbox"
                      checked={c.serious_illness}
                      onChange={(e) =>
                        run(async () => {
                          await api(`/api/families/me/children/${c.id}/serious-illness`, {
                            method: 'PATCH',
                            body: { value: e.target.checked },
                          })
                          await familyMode.refresh()
                        })
                      }
                    />
                    <span>
                      Ciężka, nieodwracalna choroba dziecka („Za życiem”)
                      {c.serious_illness && (
                        <span className="muted"> (dodaliśmy do Twojej listy świadczenia z programu „Za życiem”)</span>
                      )}
                    </span>
                  </label>
                </>
              )}
            </li>
          ))}
        </ul>
        <form className="stack" onSubmit={addChild}>
          <h3>Dodaj dziecko</h3>
          <label className="field">
            Imię
            <input value={childName} onChange={(e) => setChildName(e.target.value)} required />
          </label>
          <label className="field">
            Dziecko
            <select value={childKind} onChange={(e) => setChildKind(e.target.value as 'born' | 'expected')}>
              <option value="born">już się urodziło</option>
              <option value="expected">jest w drodze</option>
            </select>
          </label>
          <label className="field">
            {childKind === 'born' ? 'Data urodzenia' : 'Przewidywany termin porodu'}
            <input type="date" value={childDate} onChange={(e) => setChildDate(e.target.value)} required />
          </label>
          <div className="row">
            <button type="submit" className="btn">
              Dodaj dziecko
            </button>
          </div>
        </form>
      </section>
    </div>
  )
}
