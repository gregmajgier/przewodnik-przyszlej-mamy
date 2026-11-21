import { useLayoutEffect, useRef } from 'react'

const PATH_D =
  'M 100 397 C 110.2 312, 117.72 249.69, 166 199 L 190.62 173.15 A 34 34 0 1 0 141.38 173.15 L 166 199 C 203.93 238.83, 184 315, 208 315 C 232 315, 236 307.36, 256 285 L 276.12 262.5 A 27 27 0 1 0 235.88 262.5 L 256 285 C 276 307.36, 280 315, 304 315 C 328 315, 308.07 254.83, 346 215 L 367.72 192.19 A 30 30 0 1 0 324.28 192.19 L 346 215 C 394.28 265.69, 401.8 312, 412 397'

type Props = {
  className?: string
  color?: string
  duration?: number
  /** Set to false for a static logo (no draw-in). */
  animate?: boolean
}

/** mRodzina ribbon logo. Draws itself in from the bottom-left on every mount. */
export function Logo({ className, color = 'currentColor', duration = 1800, animate = true }: Props) {
  const pathRef = useRef<SVGPathElement>(null)

  useLayoutEffect(() => {
    const path = pathRef.current
    if (!path || !animate) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const length = path.getTotalLength()
    const anim = path.animate(
      [{ strokeDashoffset: length }, { strokeDashoffset: 0 }],
      { duration, easing: 'ease-in-out', fill: 'backwards' },
    )
    path.style.strokeDasharray = `${length}`
    return () => anim.cancel()
  }, [duration, animate])

  return (
    <svg
      className={className}
      viewBox="80 92 352 326"
      role="img"
      aria-label="m"
      fill="none"
    >
      <path
        ref={pathRef}
        d={PATH_D}
        stroke={color}
        strokeWidth={24}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
