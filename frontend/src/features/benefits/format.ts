/** 21424 -> "21 424 zł" (twarda spacja). */
export function formatPln(amount: number): string {
  const digits = String(Math.round(amount)).replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
  return `${digits} zł`
}

/** 9 -> "za 9 dni", 1 -> "jutro", 0 -> "dziś". */
export function daysLeftPhrase(days: number): string {
  if (days <= 0) return 'dziś'
  if (days === 1) return 'jutro'
  return `za ${days} dni`
}

export const STATUS_LABEL = {
  fits: 'Pasuje',
  maybe: 'Może ci przysługiwać',
  no: 'Nie pasuje',
} as const
