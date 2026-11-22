import { useMemo, useState } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'
import { formatPln, plural } from '../../lib/format'
import { useSession } from '../../lib/session'
import { Button } from '../../ui/Button'
import { Icon } from '../../ui/Icon'
import { Avatar, PageHeader, Pill } from '../../ui/controls'
import { BenefitSheet, STATUS_TONE } from '../benefits/BenefitSheet'
import { catMeta, categoryOf, shortAmount } from '../benefits/categories'
import { STATUS_LABEL } from '../benefits/types'
import type { BenefitMatch } from '../benefits/types'
import { useBenefits } from '../benefits/useBenefits'
import { ChildTimeline } from './ChildTimeline'
import { guidesFor, mattersOf, peopleFor, questionsFor } from './model'
import '../../ui/ui.css'
import './matters.css'

function MatterRow({ m, onOpen }: { m: BenefitMatch; onOpen: () => void }) {
  const cat = catMeta(categoryOf(m.benefit))
  const amount = shortAmount(m.benefit)
  return (
    <li>
      <button type="button" className="list-row" onClick={onOpen}>
        <span className={`icon-tile tone-${cat.tone}`}>
          <Icon name={cat.icon} size={22} />
        </span>
        <span className="list-row-main">
          <span className="list-row-title">{m.benefit.name}</span>
          <span className="list-row-sub">{m.match.status === 'maybe' ? 'Odpowiedz na pytanie, a sprawdzimy' : (m.match.reasons[0] ?? cat.label)}</span>
        </span>
        <span className="list-row-end">
          {amount ? <span className="matter-amount">{amount}</span> : <Pill tone={STATUS_TONE[m.match.status]}>{STATUS_LABEL[m.match.status]}</Pill>}
          <Icon name="chevronRight" size={18} />
        </span>
      </button>
    </li>
  )
}

export default function MattersPage() {
  const { who = '' } = useParams()
  const { user, family } = useSession()
  const { items, error, busyId, answer } = useBenefits(!!family)
  const [openId, setOpenId] = useState<string | null>(null)
  const people = useMemo(() => peopleFor(user, family), [user, family])
  const person = people.find((p) => p.key === who)

  if (family && !person) return <Navigate to="/" replace />
  if (!person) return null

  const matters = mattersOf(person.key, people, items ?? [])
  const now = matters.filter((m) => m.match.status === 'fits')
  const maybe = matters.filter((m) => m.match.status === 'maybe')
  const guides = guidesFor(person, people)
  const questions = questionsFor(person)
  const urgentGuide = guides.find((g) => g.urgent)
  const urgentNow = urgentGuide?.urgent
    ? `${urgentGuide.title.split(/ — |: /)[0]}: ${urgentGuide.urgent.charAt(0).toLowerCase()}${urgentGuide.urgent.slice(1)}`
    : undefined
  const annual = now.reduce((s, m) => s + (m.benefit.annual_value_estimate ?? 0), 0)
  const open = (items ?? []).find((m) => m.benefit.id === openId) ?? null
  const ctx = person.kind === 'family' ? 'naszej rodziny' : person.kind === 'parent' ? 'mnie' : `dziecka: ${person.name} (${person.subtitle})`

  return (
    <div className="page page-narrow matters">
      <PageHeader title={person.name} eyebrow={person.kind === 'family' ? 'Sprawy całej rodziny' : person.kind === 'parent' ? 'Twoje sprawy' : 'Sprawy dziecka'}>
        <div className="matters-hero">
          <Avatar name={person.name} tone={person.tone} icon={person.icon} size={72} />
          <div className="matters-hero-text">
            <span className="matters-sub">{person.subtitle}</span>
            <div className="row" style={{ gap: '0.4rem' }}>
              {matters.length > 0 && <Pill tone="pink">{plural(matters.length, 'sprawa', 'sprawy', 'spraw')}</Pill>}
              {matters.length === 0 && guides.length > 0 && <Pill>{plural(guides.length, 'wskazówka', 'wskazówki', 'wskazówek')}</Pill>}
              {annual > 0 && <Pill tone="green">ok. {formatPln(annual)} / rok</Pill>}
            </div>
          </div>
        </div>
      </PageHeader>

      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}

      {person.kind === 'child' && person.child && (
        <ChildTimeline child={person.child} tone={person.tone} urgent={urgentNow} />
      )}

      {!items && !error && (
        <div className="stack section" role="status" aria-label="Wczytuję sprawy">
          <div className="skeleton" style={{ height: '4.5rem' }} />
          <div className="skeleton" style={{ height: '4.5rem' }} />
        </div>
      )}

      {now.length > 0 && (
        <section className="section rise" style={{ ['--i' as string]: 1 }} aria-labelledby="now-h">
          <h2 id="now-h">{person.kind === 'parent' ? 'Urlopy i świadczenia' : 'Przysługuje'}</h2>
          <div className="card matter-card">
            <ul className="list">
              {now.map((m) => (
                <MatterRow key={m.benefit.id} m={m} onOpen={() => setOpenId(m.benefit.id)} />
              ))}
            </ul>
          </div>
        </section>
      )}

      {maybe.length > 0 && (
        <section className="section rise" style={{ ['--i' as string]: 2 }} aria-labelledby="maybe-h">
          <h2 id="maybe-h">Do sprawdzenia</h2>
          <div className="card matter-card">
            <ul className="list">
              {maybe.map((m) => (
                <MatterRow key={m.benefit.id} m={m} onOpen={() => setOpenId(m.benefit.id)} />
              ))}
            </ul>
          </div>
        </section>
      )}

      {guides.length > 0 && (
        <section className="section rise" style={{ ['--i' as string]: 3 }} aria-labelledby="guides-h">
          <h2 id="guides-h">{person.kind === 'child' ? 'Co warto wiedzieć' : 'Wskazówki'}</h2>
          <div className="guides">
            {guides.map((g) => (
              <article key={g.id} className={`guide ${g.urgent ? 'guide-urgent' : ''}`}>
                <div className="guide-head">
                  <span className="icon-tile">
                    <Icon name={g.icon} size={22} />
                  </span>
                  {g.urgent && <Pill tone="pink">{g.urgent}</Pill>}
                </div>
                <h3>{g.title}</h3>
                <p>{g.text}</p>
                {g.action && (
                  <div className="guide-action">
                    <Button to={g.action.to} size="sm" icon="arrowRight">
                      {g.action.label}
                      <span className="sr-only">: {g.title}</span>
                    </Button>
                  </div>
                )}
                {g.source && (
                  <a href={g.source.url} target="_blank" rel="noopener noreferrer" className="guide-src">
                    {g.source.label} <Icon name="external" size={14} />
                    <span className="sr-only"> (otwiera się w nowej karcie)</span>
                  </a>
                )}
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="section rise ask-card" style={{ ['--i' as string]: 4 }} aria-labelledby="ask-h">
        <div className="ask-card-head">
          <span className="ask-card-icon">
            <Icon name="sparkle" size={22} />
          </span>
          <div>
            <h2 id="ask-h">Masz pytanie?</h2>
            <span className="ask-card-sub">
              {person.kind === 'family' ? 'O sprawy całej rodziny' : person.kind === 'parent' ? 'O Twoje urlopy i świadczenia' : `Podpowiedzi dla: ${person.name}`}
            </span>
          </div>
        </div>
        <div className="ask-chips">
          {questions.map((q) => (
            <Link key={q} to="/czat" state={{ q, context: ctx, autoSend: true }} className="ask-chip">
              {q}
              <Icon name="arrowUpRight" size={16} />
            </Link>
          ))}
        </div>
      </section>

      <BenefitSheet item={open} onClose={() => setOpenId(null)} onAnswer={answer} busy={busyId === openId} />
    </div>
  )
}
