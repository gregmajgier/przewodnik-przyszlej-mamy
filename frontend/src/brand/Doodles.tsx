import type { CSSProperties } from 'react'
import { DOODLES } from './doodlePaths'

type Placement = { icon: string; x: number; y: number; size: number; rot: number; wide?: boolean }

// Pozycje w % kontenera (środek ikony). `wide` = tylko na szerszych ekranach.
const SETS: Record<'welcome' | 'analysis' | 'hero', Placement[]> = {
  welcome: [
    { icon: 'stroller', x: 14, y: 14, size: 64, rot: -10 },
    { icon: 'teddy', x: 84, y: 12, size: 64, rot: 8 },
    { icon: 'calendar', x: 8, y: 46, size: 52, rot: 6, wide: true },
    { icon: 'bottle', x: 91, y: 44, size: 54, rot: 12, wide: true },
    { icon: 'backpack', x: 18, y: 82, size: 58, rot: 8 },
    { icon: 'document', x: 82, y: 80, size: 56, rot: -8 },
    { icon: 'rattle', x: 30, y: 30, size: 44, rot: -14, wide: true },
    { icon: 'checklist', x: 70, y: 30, size: 46, rot: 10, wide: true },
  ],
  analysis: [
    { icon: 'magnifier', x: 12, y: 16, size: 58, rot: -8 },
    { icon: 'document', x: 88, y: 14, size: 56, rot: 10 },
    { icon: 'checklist', x: 8, y: 62, size: 52, rot: 6, wide: true },
    { icon: 'calendar', x: 92, y: 58, size: 52, rot: -10, wide: true },
    { icon: 'clock', x: 84, y: 88, size: 50, rot: 8 },
    { icon: 'cap', x: 14, y: 90, size: 54, rot: -6 },
  ],
  hero: [
    { icon: 'stroller', x: 72, y: 24, size: 54, rot: -10, wide: true },
    { icon: 'teddy', x: 91, y: 14, size: 50, rot: 10 },
    { icon: 'backpack', x: 86, y: 74, size: 50, rot: 8, wide: true },
    { icon: 'bottle', x: 70, y: 80, size: 44, rot: -12, wide: true },
  ],
}

const drift = (i: number) => ({
  dx: 4 + ((i * 7) % 10),
  dy: 4 + ((i * 11) % 10),
  dr: (i % 2 ? -1 : 1) * (3 + ((i * 5) % 5)),
  dur: 6 + ((i * 13) % 40) / 10,
  delay: -((i * 17) % 70) / 10,
})

/** Białe, rysunkowe ikony unoszące się w tle (jak w hero landingu). Dekoracja — ukryta dla czytników. */
export function Doodles({ set, opacity = 0.7 }: { set: keyof typeof SETS; opacity?: number }) {
  return (
    <div className="doodles" aria-hidden="true" style={{ opacity }}>
      {SETS[set].map((p, i) => {
        const d = drift(i)
        return (
          <div
            key={i}
            className={`doodle${p.wide ? ' doodle-wide' : ''}`}
            style={
              {
                '--x': `${p.x}%`,
                '--y': `${p.y}%`,
                '--s': `${p.size}px`,
                '--rot': `${p.rot}deg`,
                '--dx': `${d.dx}px`,
                '--dy': `${d.dy}px`,
                '--dr': `${d.dr}deg`,
                '--dur': `${d.dur}s`,
                '--delay': `${d.delay}s`,
                '--n': i,
              } as CSSProperties
            }
          >
            <svg viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth={3.5} strokeLinecap="round" strokeLinejoin="round">
              {(DOODLES[p.icon] ?? []).map((path, k) => (
                <path key={k} d={path} />
              ))}
            </svg>
          </div>
        )
      })}
    </div>
  )
}
