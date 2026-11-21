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
