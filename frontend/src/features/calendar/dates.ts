import { plural } from '../../lib/format'

/** Data „YYYY-MM-DD” jako lokalna północ (bez przesunięć strefy czasowej). */
export function parseDay(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function toIso(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

export const todayIso = () => toIso(new Date())

export function daysUntil(iso: string, from = todayIso()): number {
  return Math.round((parseDay(iso).getTime() - parseDay(from).getTime()) / 86_400_000)
}

/** „dziś”, „jutro”, „za 5 dni”, „wczoraj”, „3 dni temu”. */
export function relativeDay(iso: string, from = todayIso()): string {
  const n = daysUntil(iso, from)
  if (n === 0) return 'dziś'
  if (n === 1) return 'jutro'
  if (n === -1) return 'wczoraj'
  if (n > 0) return `za ${plural(n, 'dzień', 'dni', 'dni')}`
  return `${plural(-n, 'dzień', 'dni', 'dni')} temu`
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

/** „Grudzień 2026” — mianownik, do nagłówków. */
export function monthTitle(year: number, month: number): string {
  return cap(new Date(year, month, 1).toLocaleDateString('pl-PL', { month: 'long', year: 'numeric' }))
}

export const monthKey = (iso: string) => iso.slice(0, 7)

export function weekdayShort(iso: string): string {
  return parseDay(iso).toLocaleDateString('pl-PL', { weekday: 'short' }).replace('.', '')
}

export function dayLong(iso: string): string {
  return parseDay(iso).toLocaleDateString('pl-PL', { weekday: 'long', day: 'numeric', month: 'long' })
}

/** Tygodnie miesiąca (pn–nd); dni spoza miesiąca to null. */
export function monthWeeks(year: number, month: number): (string | null)[][] {
  const first = new Date(year, month, 1)
  const lead = (first.getDay() + 6) % 7
  const days = new Date(year, month + 1, 0).getDate()
  const cells: (string | null)[] = [...Array<null>(lead).fill(null)]
  for (let d = 1; d <= days; d++) cells.push(toIso(new Date(year, month, d)))
  while (cells.length % 7) cells.push(null)
  const weeks: (string | null)[][] = []
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7))
  return weeks
}
