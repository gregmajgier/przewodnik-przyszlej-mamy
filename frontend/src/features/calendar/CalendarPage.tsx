import { useState } from 'react'
import EventCard from './EventCard'
import './calendar.css'
import { isAtRisk } from './types'
import { useCalendar } from './useCalendar'

export default function CalendarPage() {
  const { events, error, busyId, toggle } = useCalendar()
  const [onlyRisk, setOnlyRisk] = useState(false)
  const [showDone, setShowDone] = useState(false)

  const visible = (events ?? []).filter((e) => (showDone || !e.done) && (!onlyRisk || isAtRisk(e)))
  const riskCount = (events ?? []).filter(isAtRisk).length

  return (
    <div className="stack">
      <h1>Kalendarz</h1>
      <p className="muted">
        Terminy wniosków, złożone wnioski i ostrzeżenia całej rodziny. Odklikaj to, co już zrobione, a drugi
        rodzic też to zobaczy.
      </p>
      <div className="row" role="group" aria-label="Filtry">
        <label className="event-done">
          <input type="checkbox" checked={onlyRisk} onChange={(e) => setOnlyRisk(e.target.checked)} />
          Tylko zagrożone ({riskCount})
        </label>
        <label className="event-done">
          <input type="checkbox" checked={showDone} onChange={(e) => setShowDone(e.target.checked)} />
          Pokaż zrobione
        </label>
      </div>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {events === null && !error && <p role="status">Ładowanie…</p>}
      {events !== null && visible.length === 0 && (
        <p className="muted">{onlyRisk ? 'Nic nie jest zagrożone. Tak trzymać!' : 'Brak wpisów.'}</p>
      )}
      {visible.length > 0 && (
        <ol className="timeline" aria-label="Wpisy kalendarza">
          {visible.map((e) => (
            <li key={e.id} className={e.done ? 'is-done' : undefined}>
              <EventCard event={e} onToggle={toggle} busy={busyId === e.id} />
            </li>
          ))}
        </ol>
      )}
      <p className="notice">Wkrótce: przypomnienia mailem i SMS-em. Na razie ostrzeżenia widzisz tutaj i na pulpicie.</p>
    </div>
  )
}
