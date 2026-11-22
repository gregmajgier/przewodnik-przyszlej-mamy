import { useEffect, useMemo, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import { formatPln, plural, timeAgo } from '../../lib/format'
import { Button } from '../../ui/Button'
import { Icon } from '../../ui/Icon'
import type { IconName } from '../../ui/Icon'
import { Pill, Segmented } from '../../ui/controls'
import './official.css'
import { NEXT_STEP, STATUS_TONE, statusLabel } from './types'
import type { BenefitStatus, OfficialBenefit, Unit } from './types'

type Filter = 'all' | BenefitStatus

const STATS: { status: BenefitStatus; label: string; icon: IconName }[] = [
  { status: 'published', label: 'Opublikowane', icon: 'eye' },
  { status: 'awaiting_approval', label: 'Do zatwierdzenia', icon: 'docCheck' },
  { status: 'draft', label: 'Szkice', icon: 'pen' },
]

const FLOW: { icon: IconName; title: string; text: string }[] = [
  { icon: 'doc', title: 'Wklej uchwałę', text: 'Nazwę, kwotę i kryteria odczytamy z tekstu.' },
  { icon: 'checkCircle', title: 'Zatwierdź warunki', text: 'Każdy warunek zamieniamy na pytanie tak/nie albo sprawdzamy z profilu.' },
  { icon: 'family', title: 'Opublikuj', text: 'Rodzice z Twojego obszaru zobaczą świadczenie w swojej bazie.' },
]

function BenefitRow({ b, i }: { b: OfficialBenefit; i: number }) {
  const perk = b.category === 'perk'
  return (
    <li className="rise" style={{ ['--i' as string]: i + 3 }}>
      <Link to={`/urzednik/swiadczenia/${b.id}`} className={`off-row is-${b.status}`}>
        <span className={`icon-tile ${perk ? 'tone-sky' : 'tone-peach'}`} aria-hidden="true">
          <Icon name={perk ? 'percent' : 'coins'} size={22} />
        </span>
        <span className="off-row-main">
          <h3>{b.name}</h3>
          <span className="off-row-meta">
            {b.amount_text && <span className="off-row-amount">{b.amount_text}</span>}
            {b.annual_value_estimate ? <span>~{formatPln(b.annual_value_estimate)} / rok</span> : null}
            {b.updated_at && <span>zmieniono {timeAgo(b.updated_at)}</span>}
          </span>
        </span>
        <span className="off-row-side">
          <Pill tone={STATUS_TONE[b.status]} dot>
            {statusLabel(b)}
          </Pill>
          <span className="off-row-next">
            {b.status === 'awaiting_approval' && b.conditions_approved ? 'Opublikuj' : NEXT_STEP[b.status]}
            <Icon name="chevronRight" size={16} />
          </span>
        </span>
      </Link>
    </li>
  )
}

export default function BenefitsList() {
  const unit = useOutletContext<Unit | null | undefined>()
  const [items, setItems] = useState<OfficialBenefit[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<Filter>('all')
  const [query, setQuery] = useState('')

  useEffect(() => {
    let cancelled = false
    api<OfficialBenefit[]>('/api/official/benefits')
      .then((r) => !cancelled && setItems(r))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.detail : 'Nie udało się pobrać świadczeń.'))
    return () => {
      cancelled = true
    }
  }, [])

  const count = (s: BenefitStatus) => items?.filter((b) => b.status === s).length ?? 0
  const shown = useMemo(() => {
    const q = query.trim().toLocaleLowerCase('pl')
    return (items ?? [])
      .filter((b) => filter === 'all' || b.status === filter)
      .filter((b) => !q || b.name.toLocaleLowerCase('pl').includes(q))
      // najpierw to, co czeka na urzędnika
      .sort((a, b) => ORDER[a.status] - ORDER[b.status])
  }, [items, filter, query])

  const waiting = count('awaiting_approval') + count('draft')

  return (
    <div className="page off-page">
      <section className="off-hero rise" aria-labelledby="off-hero-h">
        <div className="off-hero-text">
          <p className="off-hero-eyebrow">
            <Icon name="pin" size={15} /> {unit?.name ?? 'Panel samorządu'}
          </p>
          <h1 id="off-hero-h">Świadczenia Twojej jednostki</h1>
          <p className="off-hero-lead">
            {items === null
              ? 'Sprawdzam, co już opublikowaliście…'
              : waiting > 0
                ? `${plural(waiting, 'świadczenie czeka', 'świadczenia czekają', 'świadczeń czeka')} na Twój ruch. Opublikowane widzą rodzice z obszaru jednostki.`
                : 'Wszystko opublikowane. Rodzice z obszaru jednostki widzą Wasze świadczenia w swojej bazie.'}
          </p>
          <div className="off-hero-actions">
            <Button to="/urzednik/swiadczenia/nowe" icon="plus" variant="white">
              Dodaj świadczenie
            </Button>
            <Button to="/urzednik/swiadczenia/nowe?z=uchwala" leading="sparkle" variant="ghost" className="off-hero-ghost">
              Wklej uchwałę
            </Button>
          </div>
        </div>
        <dl className="off-stats">
          {STATS.map((s) => (
            <div key={s.status} className={`off-stat is-${s.status}`}>
              <dt>
                <Icon name={s.icon} size={16} /> {s.label}
              </dt>
              <dd>{items === null ? '–' : count(s.status)}</dd>
            </div>
          ))}
        </dl>
      </section>

      <div className="off-list-layout">
        <section className="off-list" aria-labelledby="off-list-h">
          <div className="section-head">
            <h2 id="off-list-h">Lista świadczeń</h2>
          </div>
          <div className="off-list-tools">
            <Segmented
              label="Filtr statusu"
              value={filter}
              onChange={setFilter}
              options={[
                { value: 'all', label: 'Wszystkie', count: items?.length ?? 0 },
                { value: 'published', label: 'Opublikowane', count: count('published') },
                { value: 'awaiting_approval', label: 'Warunki', count: count('awaiting_approval') },
                { value: 'draft', label: 'Szkice', count: count('draft') },
              ]}
            />
            <label className="off-search">
              <Icon name="search" size={18} />
              <span className="sr-only">Szukaj świadczenia</span>
              <input type="search" placeholder="Szukaj po nazwie" value={query} onChange={(e) => setQuery(e.target.value)} />
            </label>
          </div>

          {error && (
            <p role="alert" className="alert">
              {error}
            </p>
          )}
          {items === null && !error && (
            <ul className="off-rows" aria-hidden="true">
              {[0, 1, 2].map((i) => (
                <li key={i} className="skeleton off-row-skel" />
              ))}
            </ul>
          )}
          {items?.length === 0 && (
            <div className="off-empty">
              <span className="icon-tile tone-lilac" aria-hidden="true">
                <Icon name="gift" size={26} />
              </span>
              <h3>Nie dodano jeszcze żadnego świadczenia</h3>
              <p className="muted">Zacznij od uchwały: wkleisz tekst, a formularz wypełni się sam.</p>
              <Button to="/urzednik/swiadczenia/nowe?z=uchwala" leading="sparkle">
                Wklej uchwałę
              </Button>
            </div>
          )}
          {items && items.length > 0 && shown.length === 0 && <p className="muted off-none">Nic tu nie pasuje do filtra.</p>}
          {shown.length > 0 && (
            <ul className="off-rows">
              {shown.map((b, i) => (
                <BenefitRow key={b.id} b={b} i={i} />
              ))}
            </ul>
          )}
        </section>

        <aside className="off-flow rise" style={{ ['--i' as string]: 2 }} aria-labelledby="off-flow-h">
          <h2 id="off-flow-h">Od uchwały do rodzica</h2>
          <ol>
            {FLOW.map((f, i) => (
              <li key={f.title}>
                <span className="off-flow-n">{i + 1}</span>
                <div>
                  <strong>{f.title}</strong>
                  <p>{f.text}</p>
                </div>
              </li>
            ))}
          </ol>
          <p className="off-flow-note">
            <Icon name="info" size={16} /> Zamieszkanie na obszarze jednostki sprawdzamy zawsze. Świadczenia wojewódzkie widzą rodzice we
            wszystkich gminach województwa.
          </p>
        </aside>
      </div>
    </div>
  )
}

const ORDER: Record<BenefitStatus, number> = { awaiting_approval: 0, draft: 1, published: 2 }
