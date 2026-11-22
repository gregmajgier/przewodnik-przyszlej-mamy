import { useState } from 'react'
import type { KeyboardEvent } from 'react'
import { Icon } from './Icon'

const MONTHS = ['styczeń', 'luty', 'marzec', 'kwiecień', 'maj', 'czerwiec', 'lipiec', 'sierpień', 'wrzesień', 'październik', 'listopad', 'grudzień']
const MONTHS_GEN = ['stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca', 'lipca', 'sierpnia', 'września', 'października', 'listopada', 'grudnia']
const WEEKDAYS = ['Pn', 'Wt', 'Śr', 'Cz', 'Pt', 'So', 'Nd']

const pad = (n: number) => String(n).padStart(2, '0')
const toIso = (y: number, m: number, d: number) => `${y}-${pad(m + 1)}-${pad(d)}`

function parseIso(iso: string): { y: number; m: number; d: number } | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso)
  return match ? { y: Number(match[1]), m: Number(match[2]) - 1, d: Number(match[3]) } : null
}

/** Mini kalendarz pod polem daty: miesiąc i rok do wyboru, siatka dni (tydzień od poniedziałku), „Dziś” i „Zamknij”. */
export function Calendar({
  value,
  onSelect,
  onClose,
  label,
}: {
  /** ISO „RRRR-MM-DD” albo pusty tekst */
  value: string
  onSelect: (iso: string) => void
  onClose: () => void
  /** nazwa pola, np. „Przewidywany termin porodu” — do etykiety okna */
  label: string
}) {
  // „dziś” liczymy raz, przy otwarciu kalendarza (render ma pozostać czysty)
  const [now] = useState(() => new Date())
  const today = toIso(now.getFullYear(), now.getMonth(), now.getDate())
  const selected = parseIso(value)
  const [view, setView] = useState(() => ({ y: selected?.y ?? now.getFullYear(), m: selected?.m ?? now.getMonth() }))

  const years: number[] = []
  for (let y = now.getFullYear() + 3; y >= now.getFullYear() - 30; y--) years.push(y)
  if (!years.includes(view.y)) years.push(view.y)

  const first = new Date(view.y, view.m, 1)
  const lead = (first.getDay() + 6) % 7 // poniedziałek = 0
  const days = new Date(view.y, view.m + 1, 0).getDate()

  function shift(delta: number) {
    setView(({ y, m }) => {
      const total = y * 12 + m + delta
      return { y: Math.floor(total / 12), m: ((total % 12) + 12) % 12 }
    })
  }

  function onKeyDown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      e.stopPropagation()
      onClose()
    }
  }

  return (
    <div className="dp" role="dialog" aria-label={`Kalendarz: ${label}`} onKeyDown={onKeyDown}>
      <div className="dp-head">
        <button type="button" className="dp-nav" aria-label="Poprzedni miesiąc" onClick={() => shift(-1)}>
          <Icon name="chevronLeft" size={20} />
        </button>
        <select aria-label="Miesiąc" value={view.m} onChange={(e) => setView((v) => ({ ...v, m: Number(e.target.value) }))}>
          {MONTHS.map((name, i) => (
            <option key={name} value={i}>
              {name}
            </option>
          ))}
        </select>
        <select aria-label="Rok" value={view.y} onChange={(e) => setView((v) => ({ ...v, y: Number(e.target.value) }))}>
          {years.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
        <button type="button" className="dp-nav" aria-label="Następny miesiąc" onClick={() => shift(1)}>
          <Icon name="chevronRight" size={20} />
        </button>
      </div>
      <div className="dp-grid" role="grid" aria-label={`${MONTHS[view.m]} ${view.y}`}>
        {WEEKDAYS.map((w) => (
          <span key={w} className="dp-weekday" aria-hidden="true">
            {w}
          </span>
        ))}
        {Array.from({ length: lead }, (_, i) => (
          <span key={`e${i}`} aria-hidden="true" />
        ))}
        {Array.from({ length: days }, (_, i) => {
          const d = i + 1
          const iso = toIso(view.y, view.m, d)
          const isSelected = selected !== null && iso === toIso(selected.y, selected.m, selected.d)
          return (
            <button
              key={iso}
              type="button"
              className={`dp-day${isSelected ? ' is-selected' : ''}${iso === today ? ' is-today' : ''}`}
              aria-pressed={isSelected}
              aria-label={`${d} ${MONTHS_GEN[view.m]} ${view.y}`}
              onClick={() => onSelect(iso)}
            >
              {d}
            </button>
          )
        })}
      </div>
      <div className="dp-foot">
        <button type="button" className="dp-link" onClick={() => onSelect(today)}>
          Dziś
        </button>
        <button type="button" className="dp-link" onClick={onClose}>
          Zamknij
        </button>
      </div>
    </div>
  )
}
