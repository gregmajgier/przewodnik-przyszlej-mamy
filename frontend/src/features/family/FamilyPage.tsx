import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import { useSession } from '../../lib/session'
import type { Child, FamilyView } from '../../lib/types'
import { Button } from '../../ui/Button'
import { Icon } from '../../ui/Icon'
import { Avatar, PageHeader, Pill, Toggle } from '../../ui/controls'
import { Sheet } from '../../ui/Sheet'
import { NewFormsNotice } from '../situations/NewFormsNotice'
import type { HardSituation } from '../situations/newForms'
import { SituationMenu } from '../situations/SituationMenu'
import { useFamilyMode } from '../situations/useFamilyMode'
import { childLabel, childTone, describeAge } from '../matters/model'
import { AddChildSheet } from './AddChildSheet'
import '../../ui/ui.css'
import './family.css'

/** Stan nawigacji z menu konta („Ciężka sytuacja”): pokaż na górze instrukcję zgłoszenia. */
interface FamilyNavState {
  hardSituation?: boolean
}

export default function FamilyPage() {
  const { user, refresh } = useSession()
  const familyMode = useFamilyMode()
  const [view, setView] = useState<FamilyView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [addOpen, setAddOpen] = useState(false)
  const [manage, setManage] = useState<Child | null>(null)
  const [confirmRemove, setConfirmRemove] = useState(false)
  const [copied, setCopied] = useState(false)
  // komunikat „możesz złożyć N wniosków” w panelu dziecka, po zgłoszeniu sytuacji
  const [notice, setNotice] = useState<{ childId: string; situation: HardSituation } | null>(null)
  // instrukcja z menu konta: każde kliknięcie w menu (nowy `location.key`) pokazuje ją na nowo
  const location = useLocation()
  const helpKey = (location.state as FamilyNavState | null)?.hardSituation ? location.key : null
  const [dismissedHelp, setDismissedHelp] = useState<string | null>(null)
  const showHelp = helpKey !== null && helpKey !== dismissedHelp
  const helpRef = useRef<HTMLHeadingElement>(null)
  const ready = view !== null

  useEffect(() => {
    if (!showHelp || !ready) return
    window.scrollTo?.({ top: 0 })
    helpRef.current?.focus()
  }, [showHelp, helpKey, ready])

  const load = useCallback(async () => {
    try {
      setView(await api<FamilyView>('/api/families/me'))
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Nie udało się pobrać danych rodziny.')
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

  const undoLoss = (childId: string) =>
    run(async () => {
      await api(`/api/families/me/children/${childId}/situation`, { method: 'DELETE' })
      setNotice(null)
      await familyMode.refresh()
    })

  const decide = (id: string, verb: 'accept' | 'reject') =>
    run(() => api(`/api/families/me/join-requests/${id}/${verb}`, { method: 'POST' }), true)

  async function copy(code: string) {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      setCopied(false)
    }
  }

  if (!view) {
    return (
      <div className="page page-narrow">
        {error ? (
          <p role="alert" className="alert">
            {error}
          </p>
        ) : (
          <div className="skeleton" style={{ height: '14rem', marginTop: '4rem' }} role="status" aria-label="Ładowanie" />
        )}
      </div>
    )
  }

  const isOwner = view.family.owner_id === user?.id
  const kids = view.children
  const managed = manage ? kids.find((c) => c.id === manage.id) ?? null : null

  return (
    <div className="page page-narrow family">
      {showHelp && (
        <section className="hard-help" aria-labelledby="hard-help-h">
          <div className="hard-help-head">
            <h2 id="hard-help-h" ref={helpRef} tabIndex={-1}>
              Jak zgłosić trudną sytuację
            </h2>
            <button type="button" className="icon-btn" aria-label="Zamknij instrukcję" onClick={() => setDismissedHelp(helpKey)}>
              <Icon name="close" size={20} />
            </button>
          </div>
          {kids.length === 0 ? (
            <p>
              Najpierw dodaj dziecko przyciskiem „Dodaj dziecko” niżej na tej stronie. Potem zaznaczysz na jego karcie, co
              się wydarzyło.
            </p>
          ) : (
            <>
              <p>Jeśli doszło do poronienia, martwego urodzenia albo śmierci dziecka, zaznacz to na karcie dziecka poniżej:</p>
              <ol>
                <li>Na karcie dziecka kliknij przycisk z trzema kropkami.</li>
                <li>Rozwiń „Zmiana sytuacji” i wybierz, co się wydarzyło: Poronienie, Martwe urodzenie albo Śmierć dziecka.</li>
                <li>Jeśli dziecko jest ciężko i nieodwracalnie chore, włącz tam „Ciężka, nieodwracalna choroba”.</li>
              </ol>
              <p>
                Zapiszemy to w Waszych danych, pokażemy, jakie wnioski możesz teraz złożyć, i schowamy to, co do tej sytuacji
                nie pasuje. Zgłoszenie możesz cofnąć w każdej chwili w tym samym miejscu.
              </p>
              <div className="hard-help-kids">
                {kids.map((c) => (
                  <Button key={c.id} variant="secondary" size="sm" onClick={() => setManage(c)}>
                    Otwórz kartę: {childLabel(c)}
                  </Button>
                ))}
              </div>
            </>
          )}
        </section>
      )}

      <PageHeader title={view.family.name} eyebrow="Rodzina">
        <div className="family-hero">
          <div className="family-avatars">
            {view.members.map((m) => (
              <Avatar key={m.id} name={m.name} tone={m.id === user?.id ? 'peach' : 'sky'} size={56} />
            ))}
            {kids
              .filter((c) => c.situation !== 'loss')
              .map((c, i) => (
                <Avatar key={c.id} name={childLabel(c)} tone={childTone(i)} icon={c.status === 'expected' ? 'baby' : undefined} size={56} />
              ))}
          </div>
          <p className="muted">Oboje rodzice widzą sprawy dzieci i całej rodziny. Każde z Was prowadzi swoje urlopy i wnioski.</p>
        </div>
      </PageHeader>

      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}

      {view.pending_requests.length > 0 && (
        <section className="section" aria-labelledby="req-h">
          <h2 id="req-h">Prośby o dołączenie</h2>
          {view.pending_requests.map((r) => (
            <div key={r.id} className="card request-card">
              <Avatar name={r.user_name} tone="sky" size={48} />
              <div className="request-main">
                <strong>{r.user_name}</strong>
                <span className="muted small">chce dołączyć do rodziny</span>
              </div>
              <div className="request-actions">
                <Button size="sm" onClick={() => void decide(r.id, 'accept')}>
                  Akceptuj
                </Button>
                <Button size="sm" variant="secondary" onClick={() => void decide(r.id, 'reject')}>
                  Odrzuć
                </Button>
              </div>
            </div>
          ))}
        </section>
      )}

      <section className="section" aria-labelledby="members-h">
        <h2 id="members-h">Rodzice</h2>
        <div className="member-list">
          {view.members.map((m) => {
            const me = m.id === user?.id
            const content = (
              <>
                <Avatar name={m.name} tone={me ? 'peach' : 'sky'} size={52} />
                <span className="member-main">
                  <span className="member-name">
                    {m.name}
                    {me && <Pill>Ty</Pill>}
                  </span>
                  <span className="member-sub">{m.id === view.family.owner_id ? 'Założyciel rodziny' : 'Rodzic'}</span>
                </span>
                {me && <Icon name="chevronRight" size={20} className="member-go" />}
              </>
            )
            return me ? (
              <Link key={m.id} to={`/sprawy/${m.id}`} className="member-card">
                {content}
              </Link>
            ) : (
              <div key={m.id} className="member-card">
                {content}
              </div>
            )
          })}
          {view.members.length < 2 && isOwner && view.family.invite_code && (
            <div className="invite-card">
              <div className="invite-head">
                <span className="icon-tile">
                  <Icon name="link" size={22} />
                </span>
                <div>
                  <strong>Zaproś drugiego rodzica</strong>
                  <span className="muted small">Kod ważny 7 dni. Wpisze go po zalogowaniu.</span>
                </div>
              </div>
              <p className="invite-code" aria-label={`Kod zaproszenia: ${view.family.invite_code}`}>
                {view.family.invite_code}
              </p>
              <div className="share-row">
                <Button variant="secondary" size="sm" leading={copied ? 'check' : 'copy'} onClick={() => void copy(view.family.invite_code ?? '')}>
                  {copied ? 'Skopiowano' : 'Kopiuj'}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  leading="refresh"
                  onClick={() => void run(() => api('/api/families/me/invite-code', { method: 'POST' }))}
                >
                  Nowy kod
                </Button>
              </div>
            </div>
          )}
        </div>
      </section>

      <section className="section" aria-labelledby="kids-h">
        <h2 id="kids-h">Dzieci</h2>
        <div className="kid-grid">
          {kids.map((c, i) => (
            <article key={c.id} className={`kid-card tone-bg-${childTone(i)}`}>
              <div className="kid-top">
                <Avatar name={childLabel(c)} tone={childTone(i)} icon={c.status === 'expected' ? 'baby' : undefined} size={56} />
                <button type="button" className="icon-btn kid-more" aria-label={`Ustawienia: ${childLabel(c)}`} onClick={() => setManage(c)}>
                  <Icon name="more" size={22} stroke={2.6} />
                </button>
              </div>
              <h3>{childLabel(c)}</h3>
              <p className="kid-age">{describeAge(c)}</p>
              <div className="kid-tags">
                {c.serious_illness && <Pill tone="violet">„Za życiem”</Pill>}
                {c.has_disability && <Pill>Niepełnosprawność</Pill>}
                {c.situation === 'loss' && <Pill>Jesteśmy z Wami</Pill>}
              </div>
              {c.situation !== 'loss' && (
                <Link to={`/sprawy/${c.id}`} className="kid-link">
                  Sprawy <Icon name="arrowRight" size={16} />
                </Link>
              )}
            </article>
          ))}
          <button type="button" className="kid-card kid-add" onClick={() => setAddOpen(true)}>
            <span className="kid-add-icon">
              <Icon name="plus" size={24} />
            </span>
            Dodaj dziecko
          </button>
        </div>
      </section>

      <AddChildSheet open={addOpen} onClose={() => setAddOpen(false)} onAdded={async () => {
        await load()
        await refresh()
      }} />

      <Sheet
        open={managed !== null}
        onClose={() => {
          setManage(null)
          setConfirmRemove(false)
          setNotice(null)
        }}
        title={managed ? childLabel(managed) : ''}
        subtitle={managed ? describeAge(managed) : undefined}
      >
        {managed && (
          <div className="stack">
            {notice?.childId === managed.id && <NewFormsNotice situation={notice.situation} childId={managed.id} />}
            {managed.situation === 'loss' ? (
              <div className="stack">
                <p className="muted" style={{ margin: 0 }}>
                  Zmiana sytuacji została zapisana. Jesteśmy z Wami.
                </p>
                <div>
                  <Button variant="secondary" leading="history" onClick={() => void undoLoss(managed.id)}>
                    Cofnij zgłoszenie
                  </Button>
                  <p className="muted small" style={{ margin: '0.5rem 0 0' }}>
                    Możesz to zrobić w każdej chwili. Szkice wniosków o to dziecko anulowane przy zgłoszeniu nie wrócą.
                  </p>
                </div>
              </div>
            ) : (
              <>
                <div className="card" style={{ padding: '1rem' }}>
                  <Toggle
                    label="Ciężka, nieodwracalna choroba"
                    description={managed.serious_illness ? 'Dodaliśmy świadczenia z programu „Za życiem”.' : 'Pokażemy świadczenia z programu „Za życiem”.'}
                    checked={managed.serious_illness}
                    onChange={(v) =>
                      void run(async () => {
                        await api(`/api/families/me/children/${managed.id}/serious-illness`, { method: 'PATCH', body: { value: v } })
                        setNotice(v ? { childId: managed.id, situation: 'ciezka-choroba' } : null)
                        await familyMode.refresh()
                      })
                    }
                  />
                </div>
                <SituationMenu
                  child={managed}
                  onChanged={async (kind) => {
                    setNotice({ childId: managed.id, situation: kind })
                    await load()
                  }}
                />
              </>
            )}
            {!confirmRemove ? (
              <Button variant="danger" leading="trash" onClick={() => setConfirmRemove(true)}>
                Usuń dziecko z rodziny
              </Button>
            ) : (
              <div className="card stack" style={{ padding: '1rem' }}>
                <p style={{ margin: 0, fontWeight: 800 }}>Na pewno usunąć {childLabel(managed)}?</p>
                <div className="share-row">
                  <Button variant="secondary" onClick={() => setConfirmRemove(false)}>
                    Anuluj
                  </Button>
                  <Button
                    variant="danger"
                    aria-label={`Usuń dziecko ${managed.name}`}
                    onClick={() =>
                      void run(async () => {
                        await api(`/api/families/me/children/${managed.id}`, { method: 'DELETE' })
                        setManage(null)
                        setConfirmRemove(false)
                        await refresh()
                      })
                    }
                  >
                    Usuń
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </Sheet>
    </div>
  )
}
