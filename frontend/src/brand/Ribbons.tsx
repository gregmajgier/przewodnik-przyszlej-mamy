// Białe wstążki po bokach ekranu (jak na landingu): rysują się od dołu i lekko falują.
const LEFT =
  'M -30 860 C 40 760, 150 700, 120 600 C 96 520, 14 520, 36 440 C 58 360, 168 392, 156 316 C 148 262, 86 270, 92 314 C 98 360, 166 350, 176 276 C 190 170, 62 140, 78 -40'
const RIGHT =
  'M 230 -40 C 150 60, 60 120, 96 214 C 120 280, 196 270, 176 350 C 156 430, 44 400, 54 478 C 61 532, 124 524, 118 480 C 112 434, 44 444, 36 520 C 24 630, 150 680, 130 860'

export function Ribbons({ color = '#fff', className = '' }: { color?: string; className?: string }) {
  return (
    <div className={`ribbons ${className}`} aria-hidden="true">
      <svg className="ribbon ribbon-left" viewBox="0 0 200 820" preserveAspectRatio="none" fill="none">
        <path d={LEFT} pathLength={1} stroke={color} strokeWidth={13} strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      </svg>
      <svg className="ribbon ribbon-right" viewBox="0 0 200 820" preserveAspectRatio="none" fill="none">
        <path d={RIGHT} pathLength={1} stroke={color} strokeWidth={13} strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      </svg>
    </div>
  )
}
