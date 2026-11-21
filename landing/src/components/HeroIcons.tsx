// Line icons (white, round caps like the logo) floating around the hero to
// suggest how much a parent has on their mind. Each drifts in its own range.
// Positions are % of the hero (centre of the icon); `m` is the position on
// narrow screens (icons without `m` are hidden there).
const ICONS: Record<string, string[]> = {
  stroller: [
    'M12 32 H50 C50 42 42 48 31 48 C20 48 12 42 12 32 Z',
    'M31 32 V16 C42 16 50 22 50 32',
    'M50 30 L56 16',
    'M18 54 h.1 M42 54 h.1',
  ],
  bottle: [
    'M32 5 C28 5 27 9 27 12 H37 C37 9 36 5 32 5 Z',
    'M22 12 H42 a2 2 0 0 1 2 2 V18 H20 V14 a2 2 0 0 1 2 -2 Z',
    'M22 18 C18 22 18 26 18 30 V54 a5 5 0 0 0 5 5 H41 a5 5 0 0 0 5 -5 V30 C46 26 46 22 42 18',
    'M18 34 H26 M18 42 H26 M18 50 H26',
    'M28 46 q2 -3 4 0 t4 0',
  ],
  book: [
    'M32 16 C24 10 14 10 8 14 V50 C14 46 24 46 32 52 C40 46 50 46 56 50 V14 C50 10 40 10 32 16 Z',
    'M32 16 V52',
  ],
  cap: [
    'M32 12 L58 24 L32 36 L6 24 Z',
    'M16 30 V42 C16 50 48 50 48 42 V30',
    'M58 24 V42',
  ],
  rattle: [
    'M10 24 a14 14 0 1 0 28 0 a14 14 0 1 0 -28 0',
    'M24 31 C16 25 17 17 24 21.5 C31 17 32 25 24 31 Z',
    'M34 34 L48 48',
    'M58 53 a5 5 0 1 0 -10 0 a5 5 0 1 0 10 0',
  ],
  teddy: [
    'M17 30 a15 15 0 1 0 30 0 a15 15 0 1 0 -30 0',
    'M21.4 19.4 A6 6 0 1 1 29.4 15.2',
    'M42.6 19.4 A6 6 0 1 0 34.6 15.2',
    'M26 35 a6 4.5 0 1 0 12 0 a6 4.5 0 1 0 -12 0',
    'M30.5 32.5 H33.5 L32 34.5 Z',
    'M25.5 27 h.1 M38.5 27 h.1',
    'M22 44 C16 46 14 54 16 58 H48 C50 54 48 46 42 44',
  ],
  calendar: [
    'M16 14 H48 a6 6 0 0 1 6 6 V48 a6 6 0 0 1 -6 6 H16 a6 6 0 0 1 -6 -6 V20 a6 6 0 0 1 6 -6 Z',
    'M10 26 H54 M20 8 V18 M44 8 V18',
    'M22 36 h.1 M32 36 h.1 M42 36 h.1 M22 45 h.1 M32 45 h.1',
  ],
  clock: [
    'M32 10 a22 22 0 1 0 0.1 0 Z',
    'M32 20 V32 L41 38',
  ],
  checklist: [
    'M18 8 H46 a6 6 0 0 1 6 6 V50 a6 6 0 0 1 -6 6 H18 a6 6 0 0 1 -6 -6 V14 a6 6 0 0 1 6 -6 Z',
    'M20 22 l3 3 l6 -6 M34 24 H44',
    'M20 38 l3 3 l6 -6 M34 40 H44',
  ],
  magnifier: [
    'M11 27 a16 16 0 1 0 32 0 a16 16 0 1 0 -32 0',
    'M39 39 L56 56',
    'M18 24 A9 9 0 0 1 26 16',
  ],
  nappy: [
    'M8 14 H56 V28 C56 42 44 50 32 50 C20 50 8 42 8 28 Z',
    'M8 22 H56',
    'M18 14 V22 M46 14 V22',
  ],
  thermometer: [
    'M27 38 V12 a5 5 0 0 1 10 0 V38 a10 10 0 1 1 -10 0 Z',
    'M32 22 V44',
    'M32 48 h.1',
  ],
  backpack: [
    'M20 22 C20 14 44 14 44 22 V50 a6 6 0 0 1 -6 6 H26 a6 6 0 0 1 -6 -6 Z',
    'M27 14 C27 8 37 8 37 14',
    'M20 28 H44',
    'M26 38 H38 V48 H26 Z',
  ],
  blocks: [
    'M10 40 H28 V58 H10 Z',
    'M30 40 H48 V58 H30 Z',
    'M20 20 H38 V38 H20 Z',
  ],
  document: [
    'M16 6 H38 L50 18 V56 H16 Z',
    'M38 6 V18 H50',
    'M24 28 H42 M24 36 H42 M24 44 H34',
  ],
}

type Placement = {
  icon: keyof typeof ICONS
  x: number // % of hero width
  y: number // % of hero height
  size: number // px on wide screens
  rot: number // base rotation, deg
  m?: { x: number; y: number } // position on narrow screens (hidden if absent)
}

// Icons may repeat. Irregular on purpose; they fill the gaps around the copy.
const PLACEMENTS: Placement[] = [
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
  { icon: 'stroller', x: 30, y: 76, size: 70, rot: 6, m: { x: 26, y: 89 } },
  { icon: 'teddy', x: 18, y: 84, size: 84, rot: -6, m: { x: 15, y: 83 } },
  { icon: 'checklist', x: 38, y: 88, size: 60, rot: -5 },
  { icon: 'blocks', x: 47, y: 77, size: 56, rot: 6 },
  { icon: 'calendar', x: 64, y: 85, size: 66, rot: 8 },
  { icon: 'backpack', x: 80, y: 86, size: 72, rot: -8 },
  { icon: 'nappy', x: 71, y: 73, size: 52, rot: 10, m: { x: 88, y: 82 } },
  { icon: 'rattle', x: 58, y: 74, size: 56, rot: -20 },
  { icon: 'document', x: 8, y: 82, size: 60, rot: 10 },
  { icon: 'book', x: 92, y: 86, size: 60, rot: -6, m: { x: 80, y: 89 } },
  { icon: 'thermometer', x: 36, y: 72, size: 48, rot: -14 },
]

// Deterministic per-icon drift so every icon moves differently.
const drift = (i: number) => ({
  dx: 5 + ((i * 7) % 14),
  dy: 5 + ((i * 11) % 14),
  dr: (i % 2 ? -1 : 1) * (3 + ((i * 5) % 6)),
  dur: 6 + ((i * 13) % 40) / 10,
  delay: -((i * 17) % 70) / 10,
})

export function HeroIcons() {
  return (
    <div className="hero-icons" aria-hidden="true">
      {PLACEMENTS.map((p, i) => {
        const d = drift(i)
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
