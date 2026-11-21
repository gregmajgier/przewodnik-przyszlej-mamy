import type { IconName } from '../../ui/Icon'
import type { Tone } from '../../ui/controls'
import type { Benefit } from './types'

export type CatKey = 'leave' | 'monthly' | 'oneoff' | 'perks' | 'health' | 'local' | 'care'

export const CATS: { key: CatKey; label: string; icon: IconName; tone: Tone }[] = [
  { key: 'leave', label: 'Urlopy i zasiłki', icon: 'briefcase', tone: 'sky' },
  { key: 'monthly', label: 'Co miesiąc', icon: 'coins', tone: 'pink' },
  { key: 'oneoff', label: 'Jednorazowo', icon: 'gift', tone: 'peach' },
  { key: 'perks', label: 'Ulgi i zniżki', icon: 'percent', tone: 'butter' },
  { key: 'health', label: 'Zdrowie', icon: 'health', tone: 'mint' },
  { key: 'care', label: 'Opieka', icon: 'heart', tone: 'lilac' },
  { key: 'local', label: 'W Twojej gminie', icon: 'pin', tone: 'mint' },
]

const BY_ID: Record<string, CatKey> = {
  'nat-zasilek-macierzynski': 'leave',
  'nat-urlop-macierzynski': 'leave',
  'nat-urlop-rodzicielski': 'leave',
  'nat-urlop-ojcowski': 'leave',
  'nat-zasilek-chorobowy-ciaza': 'leave',
  'nat-800-plus': 'monthly',
  'nat-zasilek-rodzinny': 'monthly',
  'nat-swiadczenie-rodzicielskie': 'monthly',
  'nat-aktywny-rodzic-w-pracy': 'monthly',
  'nat-aktywny-rodzic-w-zlobku': 'monthly',
  'nat-aktywny-rodzic-w-domu': 'monthly',
  'nat-becikowe': 'oneoff',
  'nat-za-zyciem': 'oneoff',
  'nat-dobry-start': 'oneoff',
  'nat-kdr': 'perks',
  'nat-ulga-prorodzinna': 'perks',
  'nat-leki-ciaza': 'health',
  'nat-opieka-okolooporodowa': 'health',
  'nat-badania-prenatalne': 'health',
  'nat-zasilek-pielegnacyjny': 'care',
  'nat-swiadczenie-pielegnacyjne': 'care',
  'nat-rodzina-zastepcza': 'care',
}

export function categoryOf(b: Benefit): CatKey {
  if (b.scope !== 'national') return 'local'
  return BY_ID[b.id] ?? (b.category === 'perk' ? 'perks' : 'monthly')
}

export function catMeta(key: CatKey) {
  return CATS.find((c) => c.key === key) ?? CATS[1]
}

/** Krótka kwota do listy: „800 zł / mies.” zamiast długiego opisu, gdy się da. */
export function shortAmount(b: Benefit): string | null {
  const t = b.amount_text
  if (!t) return null
  const m = /(\d[\d\s]*(?:,\d+)?)\s*zł(\s*(?:\/|na|miesięcznie|mies)[^,;()]*)?/i.exec(t)
  if (m) {
    const per = m[2] ? (/(mies)/i.test(m[2]) ? ' / mies.' : '') : ''
    return `${m[1].trim()} zł${per}`
  }
  const pct = /(\d+(?:,\d+)?)\s*%/.exec(t)
  if (pct) return `${pct[1]}%`
  return t.length <= 22 ? t : null
}
