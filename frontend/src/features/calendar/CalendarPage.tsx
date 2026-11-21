import { useEffect, useMemo, useState } from 'react'
import { plural } from '../../lib/format'
import { Icon } from '../../ui/Icon'
import { PageHeader, Segmented } from '../../ui/controls'
import EventCard from './EventCard'
import { tidy } from './labels'
import './calendar.css'
import { dayLong, monthKey, monthTitle, monthWeeks, parseDay, relativeDay, todayIso } from './dates'
import { isAtRisk } from './types'
import type { CalendarEvent } from './types'
import { useCalendar } from './useCalendar'

type Tab = 'upcoming' | 'attention' | 'done'

const WEEKDAYS = ['pn', 'wt', 'śr', 'cz', 'pt', 'sb', 'nd']

const inTab = (tab: Tab) => (e: CalendarEvent) => (tab === 'done' ? e.done : tab === 'attention' ? isAtRisk(e) : !e.done)

/** Kolor kropki w siatce miesiąca: najważniejszy wpis danego dnia. */
function dotClass(list: CalendarEvent[]): string {
  if (list.every((e) => e.done)) return 'is-done'
  if (list.some(isAtRisk)) return 'is-risk'
  return list.some((e) => e.kind === 'application') ? 'is-app' : 'is-due'
}

function MonthCard({
  events,
  onPick,
}: {
  events: CalendarEvent[]
  onPick: (iso: string) => void
}) {
  const today = todayIso()
  const byDay = useMemo(() => {
    const m = new Map<string, CalendarEvent[]>()
    for (const e of events) if (e.due_date) m.set(e.due_date, [...(m.get(e.due_date) ?? []), e])
    return m
  }, [events])

  // startujemy od bieżącego miesiąca, chyba że jest pusty — wtedy od miesiąca najbliższego terminu
  const [cursor, setCursor] = useState(() => {
    const now = parseDay(today)
    const thisMonth = monthKey(today)
    const next = events
      .filter((e) => !e.done && e.due_date && e.due_date >= today)
      .map((e) => e.due_date as string)
      .sort()[0]
    const hasNow = events.some((e) => e.due_date && monthKey(e.due_date) === thisMonth)
    const start = !hasNow && next ? parseDay(next) : now
    return { y: start.getFullYear(), m: start.getMonth() }
  })
  const move = (delta: number) =>
    setCursor(({ y, m }) => {
      const d = new Date(y, m + delta, 1)
      return { y: d.getFullYear(), m: d.getMonth() }
    })

  const weeks = monthWeeks(cursor.y, cursor.m)
  const next = events
    .filter((e) => !e.done && !e.muted && e.due_date && e.due_date >= today)
    .sort((a, b) => (a.due_date as string).localeCompare(b.due_date as string))[0]
  const attention = events.filter(isAtRisk).length
  const thisMonth = events.filter((e) => !e.done && e.due_date && monthKey(e.due_date) === monthKey(today)).length

  return (
    <section className="month-card rise" aria-label="Miesiąc">
      <div className="month-head">
        <button type="button" className="icon-btn" aria-label="Poprzedni miesiąc" onClick={() => move(-1)}>
          <Icon name="chevronLeft" size={20} />
        </button>
        <h2 aria-live="polite">{monthTitle(cursor.y, cursor.m)}</h2>
        <button type="button" className="icon-btn" aria-label="Następny miesiąc" onClick={() => move(1)}>
          <Icon name="chevronRight" size={20} />
        </button>
      </div>

      <div className="month-grid" role="grid" aria-label={monthTitle(cursor.y, cursor.m)}>
        <div className="month-row month-wd" role="row">
          {WEEKDAYS.map((d) => (
            <span key={d} role="columnheader">
              {d}
            </span>
          ))}
        </div>
        {weeks.map((week, wi) => (
          <div className="month-row" role="row" key={wi}>
            {week.map((iso, di) => {
              if (!iso) return <span key={di} className="month-cell is-empty" role="gridcell" />
              const list = byDay.get(iso)
              const day = parseDay(iso).getDate()
              const cls = `month-cell${iso === today ? ' is-today' : ''}${iso < today ? ' is-past' : ''}`
              return list ? (
                <span key={iso} role="gridcell" className={cls}>
                  <button
                    type="button"
                    className="month-day has-events"
                    aria-label={`${dayLong(iso)}: ${plural(list.length, 'wpis', 'wpisy', 'wpisów')}`}
                    onClick={() => onPick(iso)}
                  >
                    {day}
                    <span className={`month-dot ${dotClass(list)}`} aria-hidden="true" />
                  </button>
                </span>
              ) : (
                <span key={iso} role="gridcell" className={cls}>
                  <span className="month-day">{day}</span>
                </span>
              )
            })}
          </div>
        ))}
      </div>

      <dl className="month-stats">
        <div>
          <dt>W tym miesiącu</dt>
          <dd>{plural(thisMonth, 'termin', 'terminy', 'terminów')}</dd>
        </div>
        <div className={attention ? 'is-risk' : undefined}>
          <dt>Wymaga uwagi</dt>
          <dd>{attention ? plural(attention, 'sprawa', 'sprawy', 'spraw') : 'nic'}</dd>
        </div>
      </dl>
      {next?.due_date && (
        <button type="button" className="month-next" onClick={() => onPick(next.due_date as string)}>
          <span className="month-next-label">Najbliżej · {relativeDay(next.due_date)}</span>
          <span className="month-next-title">{tidy(next.title)}</span>
          <Icon name="arrowRight" size={18} />
        </button>
      )}
    </section>
  )
}

export default function CalendarPage() {
  const { events, error, busyId, toggle } = useCalendar()
  const [tab, setTab] = useState<Tab>('upcoming')
  const [focus, setFocus] = useState<string | null>(null)

  const all = useMemo(() => events ?? [], [events])
  const visible = all
    .filter(inTab(tab))
    .sort((a, b) => {
      const da = a.due_date ?? '9999'
      const db = b.due_date ?? '9999'
      return tab === 'done' ? db.localeCompare(da) : da.localeCompare(db)
    })

  // grupowanie po miesiącach; wpisy bez daty na końcu
  const groups: { key: string; title: string; items: CalendarEvent[] }[] = []
  for (const e of visible) {
    const key = e.due_date ? monthKey(e.due_date) : 'none'
    let g = groups.find((x) => x.key === key)
    if (!g) {
      const title = e.due_date ? monthTitle(parseDay(e.due_date).getFullYear(), parseDay(e.due_date).getMonth()) : 'Bez daty'
      g = { key, title, items: [] }
      groups.push(g)
    }
    g.items.push(e)
  }

  /** Kliknięcie dnia w siatce: przełącza na zakładkę, w której są wpisy z tego dnia, i przewija do nich. */
  const pick = (iso: string) => {
    const day = all.filter((e) => e.due_date === iso)
    if (!day.some(inTab(tab))) setTab(day.every((e) => e.done) ? 'done' : 'upcoming')
    setFocus(iso)
  }
  useEffect(() => {
    if (!focus) return
    const el = document.querySelector<HTMLElement>(`[data-day="${focus}"]`)
    el?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
    const t = window.setTimeout(() => setFocus(null), 1600)
    return () => window.clearTimeout(t)
  }, [focus, tab])

  const counts = {
    upcoming: all.filter(inTab('upcoming')).length,
    attention: all.filter(inTab('attention')).length,
    done: all.filter(inTab('done')).length,
  }
  const empty =
    tab === 'attention' ? 'Nic nie jest zagrożone. Tak trzymać!' : tab === 'done' ? 'Jeszcze nic nie odhaczyliście.' : 'Wszystko odhaczone. Nowe terminy pojawią się tu same.'

  return (
    <div className="page cal">
      <PageHeader title="Kalendarz" eyebrow="Terminy całej rodziny" />
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {events === null && !error && (
        <p role="status" className="muted">
          Ładowanie…
        </p>
      )}

      {events !== null && (
        <div className="cal-layout">
          <MonthCard events={all} onPick={pick} />

          <section className="agenda" aria-labelledby="agenda-h">
            <h2 id="agenda-h" className="sr-only">
              Wpisy kalendarza
            </h2>
            <Segmented<Tab>
              label="Pokaż"
              value={tab}
              onChange={setTab}
              options={[
                { value: 'upcoming', label: 'Nadchodzące', count: counts.upcoming },
                { value: 'attention', label: 'Pilne', count: counts.attention },
                { value: 'done', label: 'Zrobione', count: counts.done },
              ]}
            />
            <p className="agenda-hint">
              <Icon name="family" size={16} /> Odhaczone wpisy widzi też drugi rodzic.
            </p>

            {visible.length === 0 ? (
              <div className="agenda-empty">
                <span className="icon-tile tone-mint">
                  <Icon name={tab === 'done' ? 'checkCircle' : 'sun'} size={24} />
                </span>
                <p>{empty}</p>
              </div>
            ) : (
              groups.map((g) => (
                <div key={g.key} className="agenda-group">
                  <h3 className="agenda-month">
                    {g.title}
                    <span>{plural(g.items.length, 'wpis', 'wpisy', 'wpisów')}</span>
                  </h3>
                  <ol className="agenda-list" aria-label={g.title}>
                    {g.items.map((e, i) => (
                      <li
                        key={e.id}
                        data-day={e.due_date ?? undefined}
                        className={`rise${focus && e.due_date === focus ? ' is-focus' : ''}`}
                        style={{ ['--i' as string]: Math.min(i, 6) }}
                      >
                        <EventCard event={e} onToggle={toggle} busy={busyId === e.id} />
                      </li>
                    ))}
                  </ol>
                </div>
              ))
            )}
          </section>
        </div>
      )}
    </div>
  )
}
