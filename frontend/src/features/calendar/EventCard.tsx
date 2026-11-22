import { formatDate } from '../../lib/format'
import { Icon } from '../../ui/Icon'
import { Pill } from '../../ui/controls'
import './calendar.css'
import { parseDay, relativeDay, weekdayShort } from './dates'
import { KIND_META, tidy } from './labels'
import { isAtRisk, KIND_LABEL } from './types'
import type { CalendarEvent } from './types'

/** Okrągły „odhacz” zamiast natywnego checkboxa. */
function CheckButton({ event, title, busy, onToggle }: { event: CalendarEvent; title: string; busy: boolean; onToggle: (e: CalendarEvent, done: boolean) => void }) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={event.done}
      aria-label={`Zrobione: ${title}`}
      className="check-btn"
      disabled={busy}
      onClick={() => onToggle(event, !event.done)}
    >
      <Icon name="check" size={18} stroke={2.6} />
    </button>
  )
}

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
  const title = tidy(event.title)
  const meta = KIND_META[event.kind]
  const urgent = event.kind === 'warning' && event.severity === 'high' && !event.done && !event.muted
  const cls = ['agenda-item', `kind-${event.kind}`, event.done && 'is-done', risk && 'is-risk', event.muted && 'is-muted'].filter(Boolean).join(' ')

  return (
    <article className={cls} aria-label={title}>
      <div className="agenda-date" aria-hidden="true">
        {event.due_date ? (
          <>
            <span className="agenda-day">{parseDay(event.due_date).getDate()}</span>
            <span className="agenda-wd">{weekdayShort(event.due_date)}</span>
          </>
        ) : (
          <Icon name={meta.icon} size={20} />
        )}
      </div>

      <div className="agenda-body">
        <div className="agenda-tags">
          <Pill tone={event.done ? 'neutral' : meta.tone}>
            <Icon name={meta.icon} size={13} /> {KIND_LABEL[event.kind]}
          </Pill>
          {event.overdue && !event.done && <Pill tone="pink">Po terminie</Pill>}
          {urgent && <Pill tone="pink">Pilne</Pill>}
          {event.muted && <Pill>Wstrzymane</Pill>}
          {event.due_date && (
            <span className="agenda-when">
              <span className="sr-only">{formatDate(event.due_date)}, </span>
              {event.date_label
                ? `${event.date_label.toLowerCase()} ${relativeDay(event.due_date)}`
                : event.done
                  ? 'zrobione'
                  : relativeDay(event.due_date)}
            </span>
          )}
        </div>
        <h3 className="agenda-title">{title}</h3>
        {event.summary && <p className="agenda-summary">{tidy(event.summary)}</p>}
        {(event.actor_name || event.recipient || event.effect_until) && (
          <ul className="agenda-meta">
            {event.actor_name && (
              <li>
                <Icon name="user" size={14} /> {event.actor_name}
              </li>
            )}
            {event.recipient && (
              <li>
                <Icon name="mail" size={14} /> {event.recipient}
              </li>
            )}
            {event.effect_until && (
              <li>
                <Icon name="clock" size={14} /> Obowiązuje do {formatDate(event.effect_until)}
              </li>
            )}
          </ul>
        )}
      </div>

      {onToggle && event.date_label !== 'Złożono' && (
        <CheckButton event={event} title={title} busy={busy} onToggle={onToggle} />
      )}
    </article>
  )
}
