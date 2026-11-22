import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import { markOnboarded } from '../../lib/onboarding'
import { useSession } from '../../lib/session'
import type { KnownChild, ParentProfile } from '../../lib/types'
import { Button } from '../../ui/Button'
import { Icon } from '../../ui/Icon'
import type { IconName } from '../../ui/Icon'
import { Avatar, Progress } from '../../ui/controls'
import { childTone, describeAge } from '../matters/model'
import ContractsAttachStep from '../contracts/ContractsAttachStep'
import { listDocuments } from '../contracts/documents'
import type { EmploymentDocument } from '../contracts/types'
import { AddChildSheet } from './AddChildSheet'
import { CodeInput } from './CodeInput'
import { connectMailbox, isEmail, PROVIDER_LABEL } from './gmail'
import type { Mailbox } from './gmail'
import '../../ui/ui.css'
import '../onboarding/flow.css'

type Step = 'family' | 'children' | 'partner' | 'contracts' | 'mail'
const ORDER: Step[] = ['family', 'children', 'partner', 'contracts', 'mail']

function Choice({
  icon,
  title,
  sub,
  pressed,
  onClick,
}: {
  icon: IconName
  title: string
  sub: string
  pressed: boolean
  onClick: () => void
}) {
  return (
    <button type="button" className="choice" aria-pressed={pressed} onClick={onClick}>
      <span className="icon-tile">
        <Icon name={icon} size={24} />
      </span>
      <span className="choice-main">
        <span className="choice-title">{title}</span>
        <span className="choice-sub">{sub}</span>
      </span>
      <span className="choice-check" aria-hidden="true">
        <Icon name="check" size={16} stroke={2.6} />
      </span>
    </button>
  )
}

function asChild(k: KnownChild) {
  const expected = !!k.due_date && !k.birth_date
  return {
    id: k.name,
    family_id: '',
    name: k.name,
    birth_date: k.birth_date,
    due_date: k.due_date,
    status: expected ? ('expected' as const) : ('born' as const),
    pesel: null,
    has_disability: false,
    foster: false,
    situation: null,
    situation_kind: null,
    situation_at: null,
    serious_illness: false,
  }
}

export default function OnboardingPage() {
  const { user, family, refresh } = useSession()
  const navigate = useNavigate()
  const location = useLocation()
  // Onboarding zawsze od początku (demo: każdy ma zobaczyć cały proces). Wyjątek: po dołączeniu kodem (JoinPage).
  const startAt = (location.state as { step?: Step } | null)?.step
  const [step, setStep] = useState<Step>(startAt && ORDER.includes(startAt) ? startAt : 'family')
  const [mode, setMode] = useState<'create' | 'join'>('create')
  const [joinCode, setJoinCode] = useState('')
  const [known, setKnown] = useState<KnownChild[] | null>(null)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  // dzieci już w rodzinie odznaczone przez rodzica — usuwamy je dopiero po „Dalej”
  const [removed, setRemoved] = useState<Set<string>>(new Set())
  const [addOpen, setAddOpen] = useState(false)
  const [solo, setSolo] = useState(false)
  const [copied, setCopied] = useState(false)
  const [docs, setDocs] = useState<EmploymentDocument[] | null>(null)
  const [attaching, setAttaching] = useState(false)
  const [mailbox, setMailbox] = useState<Mailbox | null>(null)
  const [otherOpen, setOtherOpen] = useState(false)
  const [otherAddress, setOtherAddress] = useState('')
  const [otherError, setOtherError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const firstName = user?.name.split(' ')[0] ?? ''

  useEffect(() => {
    if (step !== 'children' || known) return
    let cancelled = false
    api<ParentProfile>('/api/profile/me')
      .then((p) => {
        if (cancelled) return
        const existing = new Set((family?.children ?? []).map((c) => c.name))
        const fresh = p.known_children.filter((k) => !existing.has(k.name))
        setKnown(fresh)
        setSelected(new Set(fresh.map((_, i) => i)))
      })
      .catch(() => !cancelled && setKnown([]))
    return () => {
      cancelled = true
    }
  }, [step, known, family])

  useEffect(() => {
    if (step !== 'contracts' || docs) return
    let cancelled = false
    listDocuments()
      .then((list) => !cancelled && setDocs(list))
      .catch(() => !cancelled && setDocs([]))
    return () => {
      cancelled = true
    }
  }, [step, docs])

  const index = ORDER.indexOf(step)

  function back() {
    if (index === 0) navigate('/logowanie')
    else setStep(ORDER[index - 1])
  }

  async function run(action: () => Promise<void>, fallback: string) {
    setBusy(true)
    setError(null)
    try {
      await action()
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : fallback)
    } finally {
      setBusy(false)
    }
  }

  async function next() {
    if (step === 'family') {
      if (mode === 'join') {
        if (family) {
          setStep('children') // już jesteś w rodzinie — dołączanie nie jest potrzebne
          return
        }
        await run(async () => {
          // kod to zgoda założyciela: od razu jesteś w rodzinie i idziemy dalej (dzieci, partner, umowy, poczta)
          const req = await api<{ status: string }>('/api/families/join', { method: 'POST', body: { code: joinCode.trim() } })
          if (req.status === 'accepted') {
            await refresh()
            setStep('children')
          } else {
            navigate('/dolacz', { state: { sent: true, code: joinCode.trim() } })
          }
        }, 'Nie udało się wysłać prośby.')
        return
      }
      await run(async () => {
        if (!family) {
          await api('/api/families', { method: 'POST', body: {} })
          await refresh()
        }
        setStep('children')
      }, 'Nie udało się założyć rodziny.')
    } else if (step === 'children') {
      await run(async () => {
        for (const id of removed) await api(`/api/families/me/children/${id}`, { method: 'DELETE' })
        for (const [i, k] of (known ?? []).entries()) {
          if (!selected.has(i)) continue
          await api('/api/families/me/children', {
            method: 'POST',
            body: { name: k.name, birth_date: k.birth_date, due_date: k.due_date },
          })
        }
        setKnown([])
        setRemoved(new Set())
        await refresh()
        setStep('partner')
      }, 'Nie udało się zapisać dzieci.')
    } else if (step === 'partner') {
      setStep('contracts')
    } else if (step === 'contracts') {
      setStep('mail') // umowy zapisuje już sam krok (ContractsAttachStep)
    } else {
      if (user) markOnboarded(user.id)
      navigate('/analiza')
    }
  }

  async function copyCode(code: string) {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      setCopied(false)
    }
  }

  async function share(code: string) {
    const text = `Dołącz do naszej rodziny w mRodzinie. Kod zaproszenia: ${code}`
    if (typeof navigator.share === 'function') {
      try {
        await navigator.share({ title: 'mRodzina', text })
      } catch {
        // użytkownik zamknął okno udostępniania
      }
    } else {
      await copyCode(code)
    }
  }

  const code = family?.family.invite_code ?? ''
  const existingKids = family?.children ?? []
  const nextLabel =
    step === 'children'
      ? removed.size > 0
        ? 'Zapisz zmiany'
        : selected.size > 0
          ? `Dodaj dzieci (${selected.size})`
          : 'Dalej'
      : step === 'contracts'
        ? attaching
          ? 'Czytam umowy…'
          : docs?.some((d) => d.contract_id)
            ? 'Dalej'
            : 'Pomiń na razie'
      : step === 'mail'
        ? mailbox
          ? 'Sprawdź, co Wam przysługuje'
          : 'Pomiń na razie'
        : step === 'family' && mode === 'join' && !family
          ? busy
            ? 'Dołączam…'
            : 'Dołącz do rodziny'
          : 'Dalej'

  return (
    <div className="flow">
      <div className="flow-top">
        <button type="button" className="icon-btn icon-btn-solid" aria-label="Wróć" onClick={back}>
          <Icon name="arrowLeft" size={20} />
        </button>
        <Progress value={(index + 1) / (ORDER.length + 1)} label="Konfiguracja rodziny" />
      </div>

      <div className="flow-body" key={step}>
        {step === 'family' && (
          <>
            <h1 className="flow-title rise">Cześć{firstName ? `, ${firstName}` : ''}! Zacznijmy od rodziny</h1>
            <p className="flow-lead rise" style={{ ['--i' as string]: 1 }}>
              W jednym miejscu zbierzemy sprawy Twoje i dzieci, a jeśli zechcesz, także drugiego rodzica.
            </p>
            <div className="choices rise" style={{ ['--i' as string]: 2 }}>
              <Choice
                icon="home"
                title="Zakładam rodzinę"
                sub="Dla Ciebie i dzieci. Drugiego rodzica możesz zaprosić kodem, teraz albo później"
                pressed={mode === 'create'}
                onClick={() => setMode('create')}
              />
              <Choice
                icon="link"
                title="Dołączam do rodziny"
                sub="Mam kod od partnera lub partnerki"
                pressed={mode === 'join'}
                onClick={() => setMode('join')}
              />
            </div>
            {mode === 'join' && !family && (
              <div className="join-inline stack rise">
                <p className="flow-lead" style={{ margin: 0 }}>
                  Wpisz kod zaproszenia. Drugi rodzic znajdzie go w aplikacji, w zakładce Rodzina.
                </p>
                <CodeInput value={joinCode} onChange={setJoinCode} autoFocus />
              </div>
            )}
          </>
        )}

        {step === 'children' && (
          <>
            <h1 className="flow-title rise">Wasze dzieci</h1>
            <p className="flow-lead rise" style={{ ['--i' as string]: 1 }}>
              {known && known.length > 0
                ? 'Znaleźliśmy je w rejestrach. Zaznacz, kto należy do Waszej rodziny.'
                : existingKids.length > 0
                  ? 'Odznacz dziecko, które chcesz usunąć z rodziny, albo dodaj kolejne.'
                  : 'Dodaj dzieci, także to, które jest w drodze.'}
            </p>
            {!known && <div className="skeleton" style={{ height: '5rem' }} role="status" aria-label="Szukam dzieci w rejestrach" />}
            <div className="choices rise" style={{ ['--i' as string]: 2 }}>
              {existingKids.map((c, i) => {
                const on = !removed.has(c.id)
                return (
                  <button
                    key={c.id}
                    type="button"
                    role="checkbox"
                    aria-checked={on}
                    className="choice"
                    onClick={() =>
                      setRemoved((prev) => {
                        const n = new Set(prev)
                        if (n.has(c.id)) n.delete(c.id)
                        else n.add(c.id)
                        return n
                      })
                    }
                  >
                    <Avatar name={c.name} tone={childTone(i)} icon={c.status === 'expected' ? 'baby' : undefined} size={46} />
                    <span className="choice-main">
                      <span className="choice-title">{c.name}</span>
                      <span className="choice-sub">{on ? describeAge(c) : 'Zostanie usunięte z rodziny'}</span>
                    </span>
                    <span className="choice-check" aria-hidden="true">
                      <Icon name="check" size={16} stroke={2.6} />
                    </span>
                  </button>
                )
              })}
              {known?.map((k, i) => {
                const c = asChild(k)
                const on = selected.has(i)
                return (
                  <button
                    key={`${k.name}-${i}`}
                    type="button"
                    role="checkbox"
                    aria-checked={on}
                    className="choice"
                    onClick={() =>
                      setSelected((prev) => {
                        const n = new Set(prev)
                        if (n.has(i)) n.delete(i)
                        else n.add(i)
                        return n
                      })
                    }
                  >
                    <Avatar
                      name={k.name}
                      tone={childTone(existingKids.length + i)}
                      icon={c.status === 'expected' ? 'baby' : undefined}
                      size={46}
                    />
                    <span className="choice-main">
                      <span className="choice-title">{k.name}</span>
                      <span className="choice-sub">{describeAge(c)}</span>
                    </span>
                    <span className="choice-check" aria-hidden="true">
                      <Icon name="check" size={16} stroke={2.6} />
                    </span>
                  </button>
                )
              })}
              <button type="button" className="choice choice-add" onClick={() => setAddOpen(true)}>
                <Icon name="plus" size={20} /> Dodaj dziecko
              </button>
            </div>
            <AddChildSheet open={addOpen} onClose={() => setAddOpen(false)} onAdded={refresh} />
          </>
        )}

        {step === 'partner' && (
          <>
            <div className="flow-art rise">
              <Icon name="family" size={40} />
            </div>
            <h1 className="flow-title rise" style={{ ['--i' as string]: 1 }}>
              Zaproś drugiego rodzica
            </h1>
            <p className="flow-lead rise" style={{ ['--i' as string]: 2 }}>
              Wpisze ten kod po zalogowaniu i od razu dołączy do rodziny. Oboje będziecie widzieć sprawy dzieci.
            </p>
            {!solo && code && (
              <div className="rise" style={{ ['--i' as string]: 3 }}>
                <div className="code-boxes" aria-label={`Kod zaproszenia: ${code}`} role="img">
                  {code.split('').map((ch, i) => (
                    <span key={i} className="code-box">
                      {ch}
                    </span>
                  ))}
                </div>
                <p className="sr-only">Kod zaproszenia: {code}</p>
                <div className="share-row">
                  <Button variant="secondary" leading={copied ? 'check' : 'copy'} onClick={() => void copyCode(code)}>
                    {copied ? 'Skopiowano' : 'Kopiuj kod'}
                  </Button>
                  <Button variant="secondary" leading="share" onClick={() => void share(code)}>
                    Wyślij
                  </Button>
                </div>
              </div>
            )}
            <div className="choices" style={{ marginTop: '1.25rem' }}>
              <button type="button" className="choice" aria-pressed={solo} onClick={() => setSolo((s) => !s)}>
                <span className="icon-tile tone-lilac">
                  <Icon name="heart" size={22} />
                </span>
                <span className="choice-main">
                  <span className="choice-title">Wychowuję dzieci samodzielnie</span>
                  <span className="choice-sub">Drugiego rodzica możesz zaprosić w każdej chwili w zakładce Rodzina</span>
                </span>
                <span className="choice-check" aria-hidden="true">
                  <Icon name="check" size={16} stroke={2.6} />
                </span>
              </button>
            </div>
          </>
        )}

        {step === 'contracts' && (
          <>
            <div className="flow-art rise">
              <Icon name="briefcase" size={40} />
            </div>
            <h1 className="flow-title rise" style={{ ['--i' as string]: 1 }}>
              Twoje umowy o pracę
            </h1>
            <p className="flow-lead rise" style={{ ['--i' as string]: 2 }}>
              {docs && docs.length === 0
                ? 'Nie znaleźliśmy umów w e-teczce Twojego pracodawcy. Możesz dodać je później w zakładce Umowy.'
                : 'Załącz umowy, a sprawdzimy, jakie urlopy i zasiłki Ci przysługują. Asystent mRodziny będzie znał Twoje warunki zatrudnienia.'}
            </p>
            {!docs ? (
              <div className="skeleton" style={{ height: '5rem' }} role="status" aria-label="Szukam umów u pracodawcy" />
            ) : (
              <ContractsAttachStep docs={docs} onImported={setDocs} onBusyChange={setAttaching} />
            )}
          </>
        )}

        {step === 'mail' && (
          <>
            <div className="flow-art rise">
              <Icon name="mail" size={40} />
            </div>
            <h1 className="flow-title rise" style={{ ['--i' as string]: 1 }}>
              Połącz skrzynkę pocztową
            </h1>
            <p className="flow-lead rise" style={{ ['--i' as string]: 2 }}>
              Odpowiedzi z ZUS, urzędu i od pracodawcy same zaktualizują status Waszych wniosków. Nie musisz niczego
              przepisywać.
            </p>
            <div className="card stack rise" style={{ ['--i' as string]: 3 }}>
              <div className="flow-note" style={{ marginTop: 0 }}>
                <Icon name="eye" size={18} />
                <span>Czytamy wyłącznie wiadomości w sprawie Waszych wniosków. Prywatna poczta zostaje prywatna.</span>
              </div>
              {mailbox ? (
                <p className="row" style={{ margin: 0, fontWeight: 800, color: 'var(--green)' }}>
                  <Icon name="checkCircle" size={22} /> Połączono: {mailbox.address}
                </p>
              ) : (
                <>
                  <div className="mail-providers" role="group" aria-label="Wybierz pocztę">
                    {(['gmail', 'outlook'] as const).map((p) => (
                      <Button
                        key={p}
                        variant="secondary"
                        leading="mail"
                        disabled={busy}
                        onClick={() =>
                          void run(async () => {
                            setMailbox(await connectMailbox(p))
                          }, 'Nie udało się połączyć ze skrzynką.')
                        }
                      >
                        Połącz z {PROVIDER_LABEL[p]}
                      </Button>
                    ))}
                    <Button variant="secondary" leading="mail" disabled={busy} aria-expanded={otherOpen} onClick={() => setOtherOpen((o) => !o)}>
                      Inny adres e-mail
                    </Button>
                  </div>
                  {otherOpen && (
                    <form
                      className="stack"
                      noValidate
                      onSubmit={(e) => {
                        e.preventDefault()
                        if (!isEmail(otherAddress)) {
                          setOtherError('Wpisz poprawny adres e-mail, np. anna@wp.pl.')
                          return
                        }
                        setOtherError(null)
                        void run(async () => {
                          setMailbox(await connectMailbox('other', otherAddress))
                        }, 'Nie udało się połączyć ze skrzynką.')
                      }}
                    >
                      <label className="field">
                        Adres e-mail (np. Onet, WP, Interia, poczta firmowa)
                        <input
                          type="email"
                          autoComplete="email"
                          inputMode="email"
                          value={otherAddress}
                          aria-invalid={otherError ? true : undefined}
                          onChange={(e) => setOtherAddress(e.target.value)}
                        />
                      </label>
                      {otherError && (
                        <p role="alert" className="field-error" style={{ margin: 0 }}>
                          {otherError}
                        </p>
                      )}
                      <Button type="submit" disabled={busy}>
                        {busy ? 'Łączę…' : 'Połącz'}
                      </Button>
                    </form>
                  )}
                  <p className="small muted" style={{ margin: 0 }}>
                    <span className="badge-sim">SYMULACJA</span> W demo nie logujemy się do prawdziwej skrzynki. W pełnej
                    wersji zalogujesz się u swojego dostawcy poczty.
                  </p>
                </>
              )}
            </div>
          </>
        )}

        {error && (
          <p role="alert" className="alert" style={{ marginTop: '1rem' }}>
            <Icon name="alert" size={20} />
            {error}
          </p>
        )}
      </div>

      <div className="flow-foot">
        <Button block icon="arrowRight" disabled={busy || (step === 'family' && mode === 'join' && !family && !joinCode.trim()) || (step === 'children' && !known) || (step === 'contracts' && (!docs || attaching))} onClick={() => void next()}>
          {nextLabel}
        </Button>
      </div>
    </div>
  )
}
