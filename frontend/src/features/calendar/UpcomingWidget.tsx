import { Link } from 'react-router-dom'
import EventCard from './EventCard'
import { isAtRisk } from './types'
import { useCalendar } from './useCalendar'

/** Kafelek dashboardu: ostrzeżenia + najbliższe terminy. */
export default function UpcomingWidget() {
  const { events, error, busyId, toggle } = useCalendar()
  const open = (events ?? []).filter((e) => !e.done && e.kind !== 'child')
  const top = [...open.filter(isAtRisk), ...open.filter((e) => !isAtRisk(e))].slice(0, 4)
  return (
    <section className="card stack" aria-labelledby="upcoming-h">
      <h2 id="upcoming-h">Najbliższe terminy</h2>
      {error && <p className="muted">{error}</p>}
      {events === null && !error && <p role="status">Ładowanie…</p>}
      {events !== null && top.length === 0 && <p className="muted">Brak zbliżających się terminów.</p>}
      {top.map((e) => (
        <EventCard key={e.id} event={e} onToggle={toggle} busy={busyId === e.id} />
      ))}
      <Link to="/kalendarz">Cały kalendarz →</Link>
    </section>
  )
}
