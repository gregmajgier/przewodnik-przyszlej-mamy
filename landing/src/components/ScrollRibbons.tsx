import { useEffect, useMemo, useRef, useState } from 'react'
import { buildRibbon, drawnFraction, type RibbonSpec, type Size } from './ribbonPath'

// Ribbons live in document space (they scroll with the page). They start
// inside the hero, in the hero's own colour, so they are invisible there and
// appear to pour out of the first screen. They are drawn progressively as the
// page is scrolled, wander down the page with occasional loops, and only start
// to lighten once the hero is completely out of view. All ribbons share one
// opaque colour, so where they cross they merge instead of stacking.
const RIBBONS: RibbonSpec[] = [
  { x0: 0.12, startY: 0.55, phase: 0.0, loopFirst: 1.4, loopEvery: 3.2, loopDir: 1 },
  { x0: 0.5, startY: 0.7, phase: 2.2, loopFirst: 2.6, loopEvery: 3.5, loopDir: -1 },
  { x0: 0.88, startY: 0.45, phase: 4.1, loopFirst: 2.0, loopEvery: 3.8, loopDir: 1 },
]

// accent (#ef4363) -> lighter pink
const FROM = [239, 67, 99]
const TO = [249, 205, 214]

const clamp = (n: number) => Math.min(1, Math.max(0, n))

export function ScrollRibbons() {
  const svg = useRef<SVGSVGElement>(null)
  const paths = useRef<(SVGPathElement | null)[]>([])
  const [size, setSize] = useState<Size | null>(null)

  // Track the size of the container (<main>) the ribbons cover.
  useEffect(() => {
    const parent = svg.current?.parentElement
    if (!parent) return
    const measure = () =>
      setSize({
        w: parent.clientWidth,
        h: parent.scrollHeight,
        vh: window.innerHeight,
        heroH: parent.querySelector<HTMLElement>('.hero')?.offsetHeight ?? window.innerHeight,
      })
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(parent)
    window.addEventListener('resize', measure)
    return () => {
      ro.disconnect()
      window.removeEventListener('resize', measure)
    }
  }, [])

  const ribbons = useMemo(() => (size ? RIBBONS.map((r) => buildRibbon(r, size)) : []), [size])

  useEffect(() => {
    if (!size) return
    const els = paths.current.filter((p): p is SVGPathElement => p !== null)
    const lengths = els.map((p) => p.getTotalLength())
    els.forEach((p, i) => {
      p.style.strokeDasharray = `${lengths[i]}`
    })

    let frame = 0
    const update = () => {
      frame = 0
      const y = window.scrollY
      // Lightening starts only when the hero has left the viewport.
      const lighten = clamp((y - size.heroH) / (size.vh * 1.5))
      const color = `rgb(${FROM.map((c, i) => Math.round(c + (TO[i] - c) * lighten)).join(',')})`
      els.forEach((p, i) => {
        // The tip of each ribbon follows the lower part of the viewport.
        const drawn = drawnFraction(ribbons[i].maxY, y + size.vh * 0.85)
        p.style.strokeDashoffset = `${lengths[i] * (1 - drawn)}`
        p.style.stroke = color
      })
    }
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update)
    }

    update()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      window.removeEventListener('scroll', onScroll)
      if (frame) cancelAnimationFrame(frame)
    }
  }, [size, ribbons])

  const strokeWidth = size ? Math.min(14, Math.max(8, size.w * 0.009)) : 12

  return (
    <svg
      ref={svg}
      className="scroll-ribbons"
      width={size?.w ?? 0}
      height={size?.h ?? 0}
      viewBox={size ? `0 0 ${size.w} ${size.h}` : undefined}
      aria-hidden="true"
    >
      {ribbons.map((r, i) => (
        <path
          key={i}
          ref={(el) => {
            paths.current[i] = el
          }}
          d={r.d}
          fill="none"
          stroke="var(--accent)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ))}
    </svg>
  )
}
