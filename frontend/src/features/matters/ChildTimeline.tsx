import { useId, useState } from 'react'
import type { Child } from '../../lib/types'
import { Icon } from '../../ui/Icon'
import type { Tone } from '../../ui/controls'
import { childTimeline, milestoneDate, relativeIn, stageOf, type Milestone } from './timeline'

interface Props {
  child: Child
  tone: Tone
  /** pilna sprawa na teraz, np. „Dobry Start: zostało 9 dni” */
  urgent?: string
  today?: Date
}

function Item({ m, state, today }: { m: Milestone; state: 'past' | 'next'; today: Date }) {
  return (
    <li className={`tl-item tl-${state}`}>
      <span className="tl-dot" aria-hidden="true">
        <Icon name={state === 'past' ? 'check' : m.icon} size={14} stroke={2.6} />
      </span>
      <div className="tl-body">
        <div className="tl-meta">
          <span className="tl-date">{milestoneDate(m)}</span>
          {state === 'next' && <span className="tl-in">{relativeIn(m.date, today)}</span>}
        </div>
        <h3 className="tl-title">{m.title}</h3>
        {m.text && state === 'next' && <p className="tl-text">{m.text}</p>}
      </div>
    </li>
  )
}

export function ChildTimeline({ child, tone, urgent, today: todayProp }: Props) {
  const [today] = useState(() => todayProp ?? new Date())
  const [expanded, setExpanded] = useState(false)
  const headingId = useId()
  const listId = useId()
  const t = childTimeline(child, today)
  const stage = stageOf(child, today)
  if (t.all.length === 0) return null

  const nowMs = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime()
  const past = expanded ? t.all.filter((m) => m.date.getTime() <= nowMs) : t.past
  const next = expanded ? t.all.filter((m) => m.date.getTime() > nowMs) : t.next
  const hidden = t.all.length - t.past.length - t.next.length

  return (
    <section className="section timeline rise" style={{ ['--i' as string]: 0 }} aria-labelledby={headingId}>
      <h2 id={headingId}>Oś czasu</h2>
      <div className="card tl-card">
        <ol className="tl" id={listId}>
          {past.map((m) => (
            <Item key={m.id} m={m} state="past" today={today} />
          ))}
          <li className="tl-item tl-now" aria-current="step">
            <span className={`tl-dot tone-${tone}`} aria-hidden="true">
              <Icon name="pin" size={16} stroke={2.6} />
            </span>
            <div className={`tl-now-card tone-${tone}`}>
              <span className="tl-now-label">Teraz</span>
              <h3 className="tl-now-title">
                {stage.title}
                {stage.stage && <span className="tl-now-stage"> · {stage.stage}</span>}
              </h3>
              {urgent && (
                <p className="tl-now-urgent">
                  <Icon name="clock" size={16} /> {urgent}
                </p>
              )}
            </div>
          </li>
          {next.map((m) => (
            <Item key={m.id} m={m} state="next" today={today} />
          ))}
        </ol>
        {hidden > 0 && (
          <button type="button" className="tl-more" aria-expanded={expanded} aria-controls={listId} onClick={() => setExpanded((v) => !v)}>
            {expanded ? 'Zwiń oś czasu' : 'Pokaż całą oś czasu'}
            <Icon name="chevronDown" size={18} className={expanded ? 'tl-more-open' : undefined} />
          </button>
        )}
      </div>
    </section>
  )
}
