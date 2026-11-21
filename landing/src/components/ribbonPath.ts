// Pure geometry for the background ribbons: a "turtle" walks down the page
// with a gently wandering heading and occasionally draws a full loop.

export type RibbonSpec = {
  x0: number // start x, fraction of width
  startY: number // start y, in viewport heights
  phase: number // meander phase
  loopFirst: number // first loop, in viewport heights from the start
  loopEvery: number // distance between loops, in viewport heights
  loopDir: 1 | -1 // direction of the first loop (alternates afterwards)
}

export type Size = { w: number; h: number; vh: number; heroH: number }

export type Ribbon = {
  d: string
  // maxY[i]: lowest y reached by sample i or any before it (monotone).
  maxY: number[]
}

const STEP = 20
const wrap = (a: number) => Math.atan2(Math.sin(a), Math.cos(a))

export function buildRibbon(spec: RibbonSpec, { w, h, vh }: Size): Ribbon {
  const r = Math.min(70, Math.max(40, w * 0.045)) // loop radius
  const lambda = Math.max(140, w * 0.3) // meander wavelength (px / rad)
  const loopLen = 2 * Math.PI * r
  const endY = h - vh * 0.1

  let x = w * spec.x0
  let y = vh * spec.startY
  let theta = Math.PI / 2 // heading: straight down
  let nextLoop = vh * spec.loopFirst
  let loopLeft = 0
  let dir = spec.loopDir

  const pts: [number, number][] = [[x, y]]
  const maxY: number[] = [y]
  let s = 0
  for (let i = 0; i < 4000 && y < endY; i++) {
    let k: number
    if (loopLeft > 0) {
      k = dir / r
      loopLeft -= STEP
    } else {
      if (s >= nextLoop) {
        loopLeft = loopLen
        nextLoop = s + loopLen + vh * spec.loopEvery
        dir = (dir === 1 ? -1 : 1) as 1 | -1
        k = dir / r
      } else {
        // Wander widely (sometimes past the screen edges); only turn back
        // once clearly outside the page, with just a faint pull otherwise.
        const meander = (1.3 / lambda) * Math.sin(s / lambda + spec.phase)
        k = meander - 0.0015 * wrap(theta - Math.PI / 2)
        if (x < -0.12 * w || x > 1.12 * w) {
          k -= 0.01 * wrap(theta - (Math.PI / 2 + (x < 0 ? -1 : 1) * 0.9))
        }
      }
    }
    theta += k * STEP
    x += Math.cos(theta) * STEP
    y += Math.sin(theta) * STEP
    s += STEP
    pts.push([x, y])
    maxY.push(Math.max(maxY[maxY.length - 1], y))
  }

  // Catmull-Rom -> cubic Bezier
  let d = `M ${pts[0][0].toFixed(1)} ${pts[0][1].toFixed(1)}`
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)]
    const p1 = pts[i]
    const p2 = pts[i + 1]
    const p3 = pts[Math.min(pts.length - 1, i + 2)]
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6]
    const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6]
    d += ` C ${c1[0].toFixed(1)} ${c1[1].toFixed(1)}, ${c2[0].toFixed(1)} ${c2[1].toFixed(1)}, ${p2[0].toFixed(1)} ${p2[1].toFixed(1)}`
  }
  return { d, maxY }
}

// Fraction (0..1) of the ribbon that has been reached once the page is
// scrolled so that `tipY` (document y) is the lowest point to reveal.
export function drawnFraction(maxY: number[], tipY: number) {
  const n = maxY.length - 1
  if (tipY <= maxY[0]) return 0
  if (tipY >= maxY[n]) return 1
  let lo = 0
  let hi = n
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (maxY[mid] < tipY) lo = mid
    else hi = mid
  }
  return hi / n
}
