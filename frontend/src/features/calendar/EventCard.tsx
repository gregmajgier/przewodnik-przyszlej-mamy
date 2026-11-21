import { formatDate } from '../../lib/format'
import './calendar.css'
import { isAtRisk, KIND_LABEL } from './types'
import type { CalendarEvent } from './types'

export default function EventCard({
  event,
  onToggle,
  busy = false,
}: {
  event: CalendarEvent
  onToggle?: (e: CalendarEvent, done: boolean) => void
  busy?: boolean
}) {
  const risk = isAtRisk(event)
  return (
    <article
      className={`event-card stack${event.done ? ' is-done' : ''}${risk ? ' is-risk' : ''}`}
      style={{ gap: '0.4rem' }}
      aria-label={event.title}
    >
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <span className="row" style={{ gap: '0.5rem' }}>
          <span className="event-tag">{KIND_LABEL[event.kind]}</span>
          {event.overdue && !event.done && <span className="event-tag event-tag-risk">po terminie</span>}
          {event.kind === 'warning' && event.severity === 'high' && !event.done && (
            <span className="event-tag event-tag-risk">pilne</span>
          )}
        </span>
        {event.due_date && <strong>{formatDate(event.due_date)}</strong>}
      </div>
      <h3 style={{ margin: 0 }}>{event.title}</h3>
      <p style={{ margin: 0 }}>{event.summary}</p>
      {(event.actor_name || event.recipient || event.effect_until) && (
        <p className="event-meta" style={{ margin: 0 }}>
          {event.actor_name && <>Kto: {event.actor_name}. </>}
          {event.recipient && <>Do: {event.recipient}. </>}
          {event.effect_until && <>Efekt do: {formatDate(event.effect_until)}.</>}
        </p>
      )}
      {onToggle && (
        <label className="event-done">
          <input
            type="checkbox"
            checked={event.done}
            disabled={busy}
            onChange={(e) => onToggle(event, e.target.checked)}
          />
          Zrobione
        </label>
      )}
    </article>
  )
}
