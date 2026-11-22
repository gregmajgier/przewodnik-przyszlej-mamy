// Line icons (white, round caps like the logo) floating around the hero to
// suggest how much a parent has on their mind. Each drifts in its own range.
// Positions are % of the hero (centre of the icon); `m` is the position on
// narrow screens (icons without `m` are hidden there).
import { ICONS } from './lineIcons'

type Placement = {
  icon: keyof typeof ICONS
  x: number // % of hero width
  y: number // % of hero height
  size: number // px on wide screens
  rot: number // base rotation, deg
  m?: { x: number; y: number } // position on narrow screens (hidden if absent)
}

// Icons may repeat. Irregular on purpose; they fill the gaps around the copy.
const HERO_PLACEMENTS: Placement[] = [
  { icon: 'bottle', x: 22, y: 11, size: 70, rot: 12, m: { x: 15, y: 12 } },
  { icon: 'thermometer', x: 12, y: 15, size: 66, rot: 14, m: { x: 50, y: 13 } },
  { icon: 'magnifier', x: 36, y: 11, size: 60, rot: -10 },
  { icon: 'clock', x: 55, y: 9, size: 58, rot: 0 },
  { icon: 'cap', x: 70, y: 10, size: 80, rot: -12, m: { x: 85, y: 11 } },
  { icon: 'document', x: 90, y: 12, size: 64, rot: 8 },
  { icon: 'book', x: 47, y: 20, size: 56, rot: -6 },
  { icon: 'blocks', x: 24, y: 23, size: 54, rot: 8 },
  { icon: 'teddy', x: 80, y: 22, size: 62, rot: 10 },
  { icon: 'bottle', x: 62, y: 21, size: 52, rot: -14 },
  { icon: 'stroller', x: 7, y: 29, size: 96, rot: -8 },
  { icon: 'nappy', x: 6, y: 49, size: 60, rot: -12 },
  { icon: 'rattle', x: 9, y: 65, size: 80, rot: 15 },
  { icon: 'calendar', x: 16, y: 50, size: 52, rot: 6 },
  { icon: 'clock', x: 26, y: 50, size: 46, rot: 0 },
  { icon: 'magnifier', x: 25, y: 60, size: 44, rot: 12 },
  { icon: 'book', x: 93, y: 42, size: 84, rot: 10 },
  { icon: 'checklist', x: 88, y: 32, size: 52, rot: -5 },
  { icon: 'bottle', x: 74, y: 51, size: 48, rot: 14 },
  { icon: 'blocks', x: 76, y: 60, size: 44, rot: -8 },
  { icon: 'cap', x: 91, y: 70, size: 96, rot: -10 },
  { icon: 'stroller', x: 30, y: 76, size: 70, rot: 6, m: { x: 28, y: 78 } },
  { icon: 'teddy', x: 18, y: 84, size: 84, rot: -6, m: { x: 15, y: 83 } },
  { icon: 'checklist', x: 38, y: 88, size: 60, rot: -5 },
  { icon: 'blocks', x: 47, y: 77, size: 56, rot: 6 },
  { icon: 'calendar', x: 64, y: 85, size: 66, rot: 8 },
  { icon: 'backpack', x: 80, y: 86, size: 72, rot: -8 },
  { icon: 'nappy', x: 71, y: 73, size: 52, rot: 10, m: { x: 88, y: 82 } },
  { icon: 'rattle', x: 58, y: 74, size: 56, rot: -20 },
  { icon: 'document', x: 8, y: 82, size: 60, rot: 10 },
  { icon: 'book', x: 92, y: 86, size: 60, rot: -6, m: { x: 72, y: 79 } },
  { icon: 'thermometer', x: 36, y: 72, size: 48, rot: -14 },
]

const CTA_PLACEMENTS: Placement[] = [
  { icon: 'bottle', x: 10, y: 22, size: 64, rot: -10, m: { x: 14, y: 14 } },
  { icon: 'calendar', x: 30, y: 18, size: 56, rot: 6 },
  { icon: 'thermometer', x: 44, y: 12, size: 56, rot: -14, m: { x: 50, y: 12 } },
  { icon: 'clock', x: 60, y: 14, size: 52, rot: 0 },
  { icon: 'magnifier', x: 74, y: 20, size: 50, rot: -8 },
  { icon: 'cap', x: 88, y: 25, size: 80, rot: 10, m: { x: 86, y: 14 } },
  { icon: 'rattle', x: 6, y: 46, size: 70, rot: 14 },
  { icon: 'backpack', x: 20, y: 37, size: 60, rot: 8 },
  { icon: 'stroller', x: 22, y: 66, size: 80, rot: 8, m: { x: 14, y: 86 } },
  { icon: 'teddy', x: 11, y: 82, size: 76, rot: -6 },
  { icon: 'document', x: 38, y: 84, size: 56, rot: -6 },
  { icon: 'blocks', x: 49, y: 88, size: 54, rot: 8 },
  { icon: 'nappy', x: 62, y: 82, size: 56, rot: -10, m: { x: 34, y: 89 } },
  { icon: 'book', x: 80, y: 72, size: 66, rot: -8, m: { x: 58, y: 88 } },
  { icon: 'bottle', x: 78, y: 46, size: 62, rot: 12 },
  { icon: 'checklist', x: 93, y: 52, size: 60, rot: 6 },
  { icon: 'teddy', x: 90, y: 84, size: 70, rot: -8, m: { x: 86, y: 86 } },
]

// Deterministic per-icon drift so every icon moves differently.
const drift = (i: number) => ({
  dx: 5 + ((i * 7) % 14),
  dy: 5 + ((i * 11) % 14),
  dr: (i % 2 ? -1 : 1) * (3 + ((i * 5) % 6)),
  dur: 6 + ((i * 13) % 40) / 10,
  delay: -((i * 17) % 70) / 10,
})

export function HeroIcons({ variant = 'hero' }: { variant?: 'hero' | 'cta' }) {
  const placements = variant === 'cta' ? CTA_PLACEMENTS : HERO_PLACEMENTS
  const seed = variant === 'cta' ? 7 : 0
  return (
    <div className="hero-icons" aria-hidden="true">
      {placements.map((p, i) => {
        const d = drift(i + seed)
        return (
        <div
          key={i}
          className={`hero-icon${p.m ? '' : ' wide-only'}`}
          style={
            {
              '--x': `${p.x}%`,
              '--y': `${p.y}%`,
              '--mx': `${p.m?.x ?? p.x}%`,
              '--my': `${p.m?.y ?? p.y}%`,
              '--size-w': `${p.size}px`,
              '--rot': `${p.rot}deg`,
              '--dx': `${d.dx}px`,
              '--dy': `${d.dy}px`,
              '--dr': `${d.dr}deg`,
              '--dur': `${d.dur}s`,
              '--delay': `${d.delay}s`,
            } as React.CSSProperties
          }
        >
          <svg viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth={3.5} strokeLinecap="round" strokeLinejoin="round">
            {ICONS[p.icon].map((d, i) => (
              <path key={i} d={d} />
            ))}
          </svg>
        </div>
        )
      })}
    </div>
  )
}

/** One line icon from the set above, inheriting the text colour. */
export function LineIcon({ name, size = 32 }: { name: string; size?: number }) {
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} fill="none" stroke="currentColor" strokeWidth={4} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {ICONS[name].map((d, i) => (
        <path key={i} d={d} />
      ))}
    </svg>
  )
}
