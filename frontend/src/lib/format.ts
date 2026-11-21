import type { Child } from './types'

/** "2026-11-21" -> "21.11.2026" */
export function formatDate(iso: string): string {
  const [y, m, d] = iso.split('-')
  return `${d}.${m}.${y}`
}

export function describeChild(c: Pick<Child, 'status' | 'birth_date' | 'due_date'>): string {
  if (c.status === 'expected' && c.due_date) return `w drodze, termin porodu ${formatDate(c.due_date)}`
  if (c.birth_date) return `ur. ${formatDate(c.birth_date)}`
  return ''
}

/** Maskuje PESEL: widoczne tylko 4 ostatnie cyfry. */
export function maskPesel(pesel: string): string {
  return `${'•'.repeat(Math.max(pesel.length - 4, 0))}${pesel.slice(-4)}`
}

const PLN = new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN', maximumFractionDigits: 0 })

/** 12000 -> "12 000 zł" */
export function formatPln(amount: number): string {
  return PLN.format(amount)
}

/** Odmiana przez liczbę: plural(1,'sprawa','sprawy','spraw') → „1 sprawa”, 3 → „3 sprawy”, 5 → „5 spraw”. */
export function plural(n: number, one: string, few: string, many: string): string {
  if (n === 1) return `1 ${one}`
  const last = n % 10
  const lastTwo = n % 100
  if (last >= 2 && last <= 4 && !(lastTwo >= 12 && lastTwo <= 14)) return `${n} ${few}`
  return `${n} ${many}`
}

/** „przed chwilą”, „15 min temu”, „3 godz. temu”, „wczoraj”, „4 dni temu”, potem data. */
export function timeAgo(iso: string, now = new Date()): string {
  const diff = Math.max(0, now.getTime() - new Date(iso).getTime())
  const min = Math.floor(diff / 60000)
  if (min < 1) return 'przed chwilą'
  if (min < 60) return `${min} min temu`
  const h = Math.floor(min / 60)
  if (h < 24) return `${h} godz. temu`
  const d = Math.floor(h / 24)
  if (d === 1) return 'wczoraj'
  if (d < 7) return `${d} dni temu`
  return formatDate(iso.slice(0, 10))
}
