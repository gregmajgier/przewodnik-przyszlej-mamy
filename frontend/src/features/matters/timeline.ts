// Oś czasu dziecka: co było, na jakim etapie jest teraz i co przed nami — liczona z daty urodzenia
// (albo terminu porodu). Etapy szkolne według rocznika: przedszkole od września roku, w którym dziecko kończy
// 3 lata, zerówka — 6 lat, 1. klasa — 7 lat. To typowa ścieżka; dziecko może zacząć szkołę rok wcześniej
// albo później, dlatego daty rekrutacji opisujemy jako „zwykle”.
import type { IconName } from '../../ui/Icon'
import type { Child } from '../../lib/types'
import { plMonths, plYears } from './model'

export interface Milestone {
  id: string
  date: Date
  title: string
  text?: string
  icon: IconName
  /** dokładny dzień (termin ustawowy, urodziny) albo tylko miesiąc (rekrutacje, egzaminy) */
  exact: boolean
}

export interface Stage {
  /** „7 lat”, „6 miesięcy”, „W drodze” */
  title: string
  /** „1. klasa”, „przedszkole”, „termin 20.01.2027” */
  stage: string | null
}

export interface Timeline {
  /** wszystkie kamienie milowe, chronologicznie */
  all: Milestone[]
  /** dwa ostatnie, które już były */
  past: Milestone[]
  /** cztery najbliższe */
  next: Milestone[]
}

const PAST_SHOWN = 2
const NEXT_SHOWN = 4

function parse(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function addDays(d: Date, days: number): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + days)
}

function addMonths(d: Date, months: number): Date {
  const target = new Date(d.getFullYear(), d.getMonth() + months, 1)
  const last = new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate()
  return new Date(target.getFullYear(), target.getMonth(), Math.min(d.getDate(), last))
}

function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate())
}

function fullMonths(from: Date, to: Date): number {
  let m = (to.getFullYear() - from.getFullYear()) * 12 + (to.getMonth() - from.getMonth())
  if (to.getDate() < from.getDate()) m -= 1
  return m
}

/** Rok, w którym zaczął się bieżący rok szkolny (od września). */
function schoolYear(today: Date): number {
  return today.getMonth() >= 8 ? today.getFullYear() : today.getFullYear() - 1
}

function pad(n: number): string {
  return String(n).padStart(2, '0')
}

export function stageOf(child: Child, today = new Date()): Stage {
  if (child.status === 'expected' || !child.birth_date) {
    const due = child.due_date ? parse(child.due_date) : null
    return { title: 'W drodze', stage: due ? `termin ${pad(due.getDate())}.${pad(due.getMonth() + 1)}.${due.getFullYear()}` : null }
  }
  const birth = parse(child.birth_date)
  const months = Math.max(0, fullMonths(birth, startOfDay(today)))
  const title = months < 24 ? plMonths(months) : plYears(Math.floor(months / 12))
  const y = birth.getFullYear()
  const s = schoolYear(today)
  let stage: string | null = null
  if (s >= y + 3 && s <= y + 5) stage = 'przedszkole'
  else if (s === y + 6) stage = 'zerówka'
  else if (s >= y + 7 && s <= y + 14) stage = `${s - (y + 7) + 1}. klasa`
  else if (s >= y + 15 && s <= y + 19) stage = `${s - (y + 15) + 1}. klasa szkoły średniej`
  return { title, stage }
}

function plDays(n: number): string {
  return n === 1 ? '1 dzień' : `${n} dni`
}

function plWeeks(n: number): string {
  if (n === 1) return '1 tydzień'
  const last = n % 10
  const lastTwo = n % 100
  return last >= 2 && last <= 4 && !(lastTwo >= 12 && lastTwo <= 14) ? `${n} tygodnie` : `${n} tygodni`
}

/** „jutro”, „za 4 dni”, „za 2 tygodnie”, „za 7 miesięcy”, „za 2 lata”. */
export function relativeIn(date: Date, today = new Date()): string {
  const from = startOfDay(today)
  const days = Math.round((startOfDay(date).getTime() - from.getTime()) / 86400000)
  if (days <= 0) return 'dziś'
  if (days === 1) return 'jutro'
  if (days < 14) return `za ${plDays(days)}`
  if (days < 60) return `za ${plWeeks(Math.round(days / 7))}`
  const months = fullMonths(from, startOfDay(date))
  if (months < 24) return `za ${plMonths(Math.max(2, months))}`
  return `za ${plYears(Math.floor(months / 12))}`
}

const MONTHS = ['styczeń', 'luty', 'marzec', 'kwiecień', 'maj', 'czerwiec', 'lipiec', 'sierpień', 'wrzesień', 'październik', 'listopad', 'grudzień']
const MONTHS_GEN = ['stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca', 'lipca', 'sierpnia', 'września', 'października', 'listopada', 'grudnia']

/** „1 lipca 2027” dla dokładnych dat, „luty 2029” dla przybliżonych. */
export function milestoneDate(m: Milestone): string {
  const d = m.date
  return m.exact ? `${d.getDate()} ${MONTHS_GEN[d.getMonth()]} ${d.getFullYear()}` : `${MONTHS[d.getMonth()]} ${d.getFullYear()}`
}

function milestones(child: Child, today: Date): Milestone[] {
  const expected = child.status === 'expected' || !child.birth_date
  const iso = expected ? child.due_date : child.birth_date
  if (!iso) return []
  const birth = parse(iso)
  const y = birth.getFullYear()
  const at = (year: number, month: number, day: number) => new Date(year, month - 1, day)

  const out: Milestone[] = [
    {
      id: 'birth',
      date: birth,
      title: 'Narodziny',
      text: expected ? 'Przewidywany termin porodu.' : undefined,
      icon: 'baby',
      exact: true,
    },
    {
      id: 'usc',
      date: addDays(birth, 21),
      title: 'Zgłoszenie urodzenia',
      text: '21 dni na zgłoszenie w urzędzie stanu cywilnego albo online. Dziecko dostaje wtedy PESEL.',
      icon: 'doc',
      exact: true,
    },
    {
      id: '800',
      date: addMonths(birth, 3),
      title: 'Wniosek o 800+',
      text: 'Złożony w ciągu 3 miesięcy od urodzenia, a świadczenie przychodzi z wyrównaniem od narodzin.',
      icon: 'coins',
      exact: true,
    },
    {
      id: 'roczek',
      date: addMonths(birth, 12),
      title: 'Roczek',
      text: 'Od 12. miesiąca „Aktywny rodzic”: dopłata do żłobka, do opiekunki albo gdy wracacie do pracy.',
      icon: 'stroller',
      exact: true,
    },
    {
      id: 'przedszkole-nabor',
      date: at(y + 3, 2, 1),
      title: 'Rekrutacja do przedszkola',
      text: 'Nabór do przedszkoli publicznych rusza zwykle w lutym roku, w którym dziecko kończy 3 lata.',
      icon: 'blocks',
      exact: false,
    },
    { id: 'przedszkole', date: at(y + 3, 9, 1), title: 'Przedszkole', icon: 'blocks', exact: true },
    {
      id: 'zerowka-nabor',
      date: at(y + 6, 2, 1),
      title: 'Zapisy do zerówki',
      text: 'Zerówka może być w przedszkolu albo w szkole. Zapisy zwykle w lutym i marcu.',
      icon: 'doc',
      exact: false,
    },
    {
      id: 'zerowka',
      date: at(y + 6, 9, 1),
      title: 'Zerówka',
      text: 'Roczne przygotowanie przedszkolne jest obowiązkowe.',
      icon: 'blocks',
      exact: true,
    },
    {
      id: 'szkola-nabor',
      date: at(y + 7, 3, 1),
      title: 'Zapisy do 1. klasy',
      text: 'Do szkoły obwodowej dziecko przyjmuje się na podstawie zgłoszenia, zwykle w marcu.',
      icon: 'doc',
      exact: false,
    },
    { id: 'szkola', date: at(y + 7, 9, 1), title: '1. klasa', icon: 'backpack', exact: true },
    {
      id: 'e8',
      date: at(y + 15, 5, 1),
      title: 'Egzamin ósmoklasisty',
      text: 'Na koniec 8. klasy. Zaraz potem rekrutacja do szkoły średniej, zwykle od maja do lipca.',
      icon: 'doc',
      exact: false,
    },
    { id: 'srednia', date: at(y + 15, 9, 1), title: 'Szkoła średnia', icon: 'school', exact: true },
    {
      id: '18',
      date: addMonths(birth, 18 * 12),
      title: '18. urodziny',
      text: 'Koniec 800+. Zasiłek rodzinny i Dobry Start mogą trwać dłużej, jeśli dziecko dalej się uczy.',
      icon: 'calendar',
      exact: true,
    },
    {
      id: 'matura',
      date: at(y + 19, 5, 1),
      title: 'Matura',
      text: 'W liceum na koniec 4. klasy, w technikum rok później.',
      icon: 'school',
      exact: false,
    },
  ]

  // Dobry Start wraca co roku — pokazujemy tylko najbliższy nabór, gdy dziecko będzie już w szkole (do 20 lat).
  const t = startOfDay(today)
  let ds = at(t.getFullYear(), 7, 1)
  if (ds <= t) ds = at(t.getFullYear() + 1, 7, 1)
  if (!expected && ds.getFullYear() >= y + 7 && ds < addMonths(birth, 20 * 12)) {
    out.push({
      id: 'dobry-start',
      date: ds,
      title: 'Dobry Start: nabór wniosków',
      text: '300 zł na wyprawkę szkolną. Wnioski w ZUS od 1 lipca do 30 listopada.',
      icon: 'backpack',
      exact: true,
    })
  }
  return out.sort((a, b) => a.date.getTime() - b.date.getTime())
}

export function childTimeline(child: Child, today = new Date()): Timeline {
  const all = milestones(child, today)
  const t = startOfDay(today).getTime()
  const done = all.filter((m) => m.date.getTime() <= t)
  const ahead = all.filter((m) => m.date.getTime() > t)
  return { all, past: done.slice(-PAST_SHOWN), next: ahead.slice(0, NEXT_SHOWN) }
}
