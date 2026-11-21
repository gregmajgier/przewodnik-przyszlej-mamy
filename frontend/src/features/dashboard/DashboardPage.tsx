import { useEffect, useMemo } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { Doodles } from '../../brand/Doodles'
import { formatDate, formatPln, plural, timeAgo } from '../../lib/format'
import { useSession } from '../../lib/session'
import { useApi } from '../../lib/useApi'
import { Icon } from '../../ui/Icon'
import { Avatar, Pill } from '../../ui/controls'
import type { BenefitMatch, Summary } from '../benefits/types'
import type { CalendarEvent } from '../calendar/types'
import { STATUS_LABEL } from '../applications/types'
import { isOpen, latestMessage, senderLabel, STATUS_TONE, useApplications } from '../applications/useApplications'
import { connectedGmail } from '../family/gmail'
import { guidesFor, mattersOf, peopleFor } from '../matters/model'
import type { Person } from '../matters/model'
import './dashboard.css'

function greeting(now = new Date()): string {
  const h = now.getHours()
  if (h < 5 || h >= 18) return 'Dobry wieczór'
  if (h < 11) return 'Dzień dobry'
  return 'Cześć'
}

function PersonTile({ person, count, preview, urgent, i }: { person: Person; count: number; preview: string; urgent?: string; i: number }) {
  const family = person.kind === 'family'
  return (
    <Link
      to={`/sprawy/${person.key}`}
      className={`person-tile tone-bg-${person.tone} ${family ? 'person-tile-family' : ''} rise`}
      style={{ ['--i' as string]: i + 2 }}
    >
      <div className="person-tile-top">
        <Avatar name={person.name} tone={person.tone} icon={person.icon} size={family ? 52 : 46} />
        <span className="person-tile-go" aria-hidden="true">
          <Icon name="arrowUpRight" size={18} />
        </span>
      </div>
      <div className="person-tile-body">
        <span className="person-tile-name">{person.name}</span>
        <span className="person-tile-sub">{person.subtitle}</span>
      </div>
      <div className="person-tile-foot">
        <span className="person-tile-count">{count > 0 ? plural(count, 'sprawa', 'sprawy', 'spraw') : 'Wskazówki'}</span>
        {urgent ? <span className="person-tile-urgent">{urgent}</span> : preview && <span className="person-tile-preview">{preview}</span>}
      </div>
    </Link>
  )
}

export default function DashboardPage() {
  const { user, family } = useSession()
  const summary = useApi<Summary>(family ? '/api/summary' : null)
  const benefits = useApi<BenefitMatch[]>(family ? '/api/benefits' : null)
  const calendar = useApi<CalendarEvent[]>(family ? '/api/calendar' : null)
  const apps = useApplications(!!family)
  const gmail = connectedGmail()

  // przy wejściu na panel dociągamy nowe odpowiedzi z poczty (status wniosków aktualizuje się sam)
  const { sync } = apps
  useEffect(() => {
    if (family) void sync()
  }, [family, sync])

  const people = useMemo(() => peopleFor(user, family), [user, family])

  if (!family) return <Navigate to="/start" replace />

  const firstName = user?.name.split(' ')[0] ?? ''
  const items = benefits.data ?? []
  const forYou = items.filter((b) => b.match.status !== 'no')
  const maybe = items.filter((b) => b.match.status === 'maybe').length
  const openApps = (apps.apps ?? []).filter((a) => isOpen(a.status))
  const recentApps = [...openApps, ...(apps.apps ?? []).filter((a) => !isOpen(a.status))].slice(0, 3)
  const upcoming = (calendar.data ?? [])
    .filter((e) => !e.done && !e.muted && e.kind !== 'child' && e.due_date)
    .sort((a, b) => (a.due_date ?? '').localeCompare(b.due_date ?? ''))
    .slice(0, 3)
  const deadline = summary.data?.nearest_deadline
  const today = new Date().toLocaleDateString('pl-PL', { weekday: 'long', day: 'numeric', month: 'long' })

  return (
    <div className="page dash">
      <section className="dash-hero rise" aria-labelledby="dash-hello">
        <Doodles set="hero" opacity={0.5} />
        <div className="dash-hero-copy">
          <p className="dash-date">{today}</p>
          <h1 id="dash-hello">
            {greeting()}, {firstName}!
          </h1>
          <p className="dash-lead">
            {summary.data ? (
              <>
                Znaleźliśmy dla Was <strong>{plural(forYou.length || summary.data.totals.fits + summary.data.totals.maybe, 'świadczenie', 'świadczenia', 'świadczeń')}</strong>
                {deadline && (
                  <>
                    . Najbliższy termin: <strong>{deadline.benefit_name}</strong> — {formatDate(deadline.date)}
                  </>
                )}
                .
              </>
            ) : summary.error ? (
              <span role="alert">{summary.error}</span>
            ) : (
              'Sprawdzam, co u Was słychać…'
            )}
          </p>
          {summary.data && summary.data.estimated_annual_total > 0 && (
            <div className="dash-hero-stats">
              <span className="dash-stat">
                <strong>{formatPln(summary.data.estimated_annual_total)}</strong>
                <span>szacunkowo rocznie</span>
              </span>
              <span className="dash-stat">
                <strong>{openApps.length}</strong>
                <span>{openApps.length === 1 ? 'wniosek w toku' : 'wnioski w toku'}</span>
              </span>
            </div>
          )}
        </div>
      </section>

      <section className="section" aria-labelledby="people-h">
        <div className="section-head">
          <h2 id="people-h">Wasze sprawy</h2>
          <Link to="/rodzina" className="section-link">
            Rodzina <Icon name="arrowRight" size={16} />
          </Link>
        </div>
        <div className="people-grid">
          {people.map((p, i) => {
            const matters = mattersOf(p.key, people, items)
            const guides = guidesFor(p, people)
            const urgent = guides.find((g) => g.urgent)
            return (
              <PersonTile
                key={p.key}
                person={p}
                i={i}
                count={matters.length}
                preview={matters
                  .slice(0, 2)
                  .map((m) => m.benefit.name.replace(/\s*\(.*\)$/, ''))
                  .join(' · ') || guides[0]?.title || ''}
                urgent={urgent ? `${urgent.title.split(' — ')[0]}: ${urgent.urgent}` : undefined}
              />
            )
          })}
        </div>
      </section>

      <section className="section" aria-labelledby="short-h">
        <div className="section-head">
          <h2 id="short-h">Na skróty</h2>
        </div>
        <div className="bento">
          <Link to="/wnioski" className="bento-tile bento-apps rise" style={{ ['--i' as string]: 1 }}>
            <div className="bento-head">
              <span className="icon-tile tone-sky">
                <Icon name="docCheck" size={24} />
              </span>
              <span className="bento-title">
                Wnioski
                <span className="bento-sub">{apps.apps ? `${openApps.length} w toku` : 'Wczytuję…'}</span>
              </span>
              <Icon name="arrowUpRight" size={20} className="bento-go" />
            </div>
            <ul className="bento-apps-list">
              {recentApps.map((a) => {
                const last = latestMessage(apps.threadOf(a.id))
                return (
                  <li key={a.id}>
                    <span className="bento-app-name">{apps.titleOf(a.form_code)}</span>
                    <Pill tone={STATUS_TONE[a.status]} dot>
                      {STATUS_LABEL[a.status]}
                    </Pill>
                    {last && (
                      <span className="bento-app-mail">
                        <Icon name="mail" size={15} /> {senderLabel(last)} · {timeAgo(last.received_at)}
                      </span>
                    )}
                  </li>
                )
              })}
              {apps.apps && recentApps.length === 0 && <li className="muted">Nie macie jeszcze wniosków.</li>}
            </ul>
            {gmail && (
              <span className="bento-sync">
                <span className={`sync-dot ${apps.syncing ? 'is-busy' : ''}`} aria-hidden="true" />
                {apps.syncing ? 'Sprawdzam Gmail…' : 'Gmail połączony — statusy aktualizują się same'}
              </span>
            )}
          </Link>

          <Link to="/swiadczenia" className="bento-tile bento-benefits rise" style={{ ['--i' as string]: 2 }}>
            <div className="bento-head">
              <span className="icon-tile">
                <Icon name="coins" size={24} />
              </span>
              <span className="bento-title">
                Baza świadczeń
                <span className="bento-sub">Wszystko, co przysługuje rodzinom</span>
              </span>
              <Icon name="arrowUpRight" size={20} className="bento-go" />
            </div>
            <div className="bento-numbers">
              <span>
                <strong>{benefits.data ? forYou.length - maybe : '–'}</strong> dla Was
              </span>
              <span>
                <strong>{benefits.data ? maybe : '–'}</strong> do sprawdzenia
              </span>
            </div>
          </Link>

          <Link to="/kalendarz" className="bento-tile bento-wide rise" style={{ ['--i' as string]: 3 }}>
            <div className="bento-head">
              <span className="icon-tile tone-butter">
                <Icon name="calendar" size={24} />
              </span>
              <span className="bento-title">
                Kalendarz
                <span className="bento-sub">Terminy i przypomnienia</span>
              </span>
              <Icon name="arrowUpRight" size={20} className="bento-go" />
            </div>
            <ul className="bento-dates">
              {upcoming.map((e) => (
                <li key={e.id}>
                  <span className="bento-date">
                    {new Date(`${e.due_date}T00:00:00`).toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' })}
                  </span>
                  <span className="bento-date-title">{apps.humanize(e.title)}</span>
                </li>
              ))}
              {calendar.data && upcoming.length === 0 && <li className="muted">Brak zbliżających się terminów.</li>}
            </ul>
          </Link>

          <Link to="/rodzina" className="bento-tile rise" style={{ ['--i' as string]: 4 }}>
            <div className="bento-head">
              <span className="icon-tile tone-mint">
                <Icon name="family" size={24} />
              </span>
              <span className="bento-title">
                Rodzina
                <span className="bento-sub">
                  {family.pending_requests.length > 0
                    ? `${plural(family.pending_requests.length, 'prośba czeka', 'prośby czekają', 'próśb czeka')} na akceptację`
                    : `${plural(family.members.length, 'rodzic', 'rodziców', 'rodziców')} · ${plural(family.children.length, 'dziecko', 'dzieci', 'dzieci')}`}
                </span>
              </span>
              <Icon name="arrowUpRight" size={20} className="bento-go" />
            </div>
            <div className="avatar-stack">
              {family.members.map((m) => (
                <Avatar key={m.id} name={m.name} tone={m.id === user?.id ? 'peach' : 'sky'} size={40} />
              ))}
              {people
                .filter((p) => p.kind === 'child')
                .map((p) => (
                  <Avatar key={p.key} name={p.name} tone={p.tone} icon={p.icon} size={40} />
                ))}
            </div>
          </Link>
        </div>
      </section>
    </div>
  )
}
