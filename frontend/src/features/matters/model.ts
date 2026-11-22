// Sprawy domowników: kto jest w rodzinie (z punktu widzenia zalogowanego rodzica), które świadczenia dotyczą kogo
// (wg roli i wieku) oraz praktyczne wskazówki. Rodzic widzi rodzinę, siebie i dzieci — bez spraw drugiego rodzica.
import type { IconName } from '../../ui/Icon'
import type { Tone } from '../../ui/controls'
import type { Child, FamilyView, User } from '../../lib/types'
import type { BenefitMatch } from '../benefits/types'

export type PersonKind = 'family' | 'parent' | 'child'

export interface Person {
  /** „rodzina” albo id użytkownika / dziecka */
  key: string
  kind: PersonKind
  name: string
  /** krótko: „Ty”, „7 lat”, „termin 20.01.2027” */
  subtitle: string
  tone: Tone
  icon?: IconName
  child?: Child
  /** wiek w miesiącach (dzieci urodzone); dla dziecka w drodze: ujemna liczba miesięcy do terminu */
  months?: number
}

export const FAMILY_KEY = 'rodzina'

export const CHILD_TONES: Tone[] = ['mint', 'sky', 'butter', 'lilac', 'pink']

/** Odcień awatara dziecka — ten sam na wszystkich ekranach (kolejność dzieci w rodzinie). */
export function childTone(index: number): Tone {
  return CHILD_TONES[index % CHILD_TONES.length]
}

function monthsBetween(fromIso: string, to: Date): number {
  const from = new Date(`${fromIso}T00:00:00`)
  let m = (to.getFullYear() - from.getFullYear()) * 12 + (to.getMonth() - from.getMonth())
  if (to.getDate() < from.getDate()) m -= 1
  return m
}

/** 1 rok, 2–4 lata, 5–21 lat, 22–24 lata… */
export function plYears(n: number): string {
  if (n === 1) return '1 rok'
  const last = n % 10
  const lastTwo = n % 100
  if (last >= 2 && last <= 4 && !(lastTwo >= 12 && lastTwo <= 14)) return `${n} lata`
  return `${n} lat`
}

export function plMonths(n: number): string {
  if (n === 1) return '1 miesiąc'
  const last = n % 10
  const lastTwo = n % 100
  if (last >= 2 && last <= 4 && !(lastTwo >= 12 && lastTwo <= 14)) return `${n} miesiące`
  return `${n} miesięcy`
}

function shortDate(iso: string): string {
  const [y, m, d] = iso.split('-')
  return `${d}.${m}.${y}`
}

export function childMonths(c: Child, today = new Date()): number | undefined {
  if (c.status === 'expected' && c.due_date) return -Math.max(0, -monthsBetween(c.due_date, today))
  if (c.birth_date) return monthsBetween(c.birth_date, today)
  return undefined
}

export function describeAge(c: Child, today = new Date()): string {
  if (c.status === 'expected') return c.due_date ? `w drodze · termin ${shortDate(c.due_date)}` : 'w drodze'
  const m = childMonths(c, today)
  if (m === undefined) return ''
  if (m < 24) return plMonths(Math.max(0, m))
  return plYears(Math.floor(m / 12))
}

/** Imię do wyświetlenia: dziecko w drodze z danych ZUS nazywa się „Dziecko w drodze” → „Maleństwo”. */
export function childLabel(c: Child): string {
  return c.status === 'expected' && /w drodze/i.test(c.name) ? 'Maleństwo' : c.name
}

export function peopleFor(user: User | null, family: FamilyView | null, today = new Date()): Person[] {
  if (!user || !family) return []
  const out: Person[] = [
    { key: FAMILY_KEY, kind: 'family', name: 'Cała rodzina', subtitle: family.family.name, tone: 'pink', icon: 'home' },
    { key: user.id, kind: 'parent', name: user.name.split(' ')[0] ?? user.name, subtitle: 'Ty', tone: 'peach' },
  ]
  family.children
    .filter((c) => c.situation !== 'loss')
    .forEach((c, i) =>
      out.push({
        key: c.id,
        kind: 'child',
        name: childLabel(c),
        subtitle: describeAge(c, today),
        tone: CHILD_TONES[i % CHILD_TONES.length],
        icon: c.status === 'expected' ? 'baby' : undefined,
        child: c,
        months: childMonths(c, today),
      }),
    )
  return out
}

// ---------- przypisanie świadczeń do osób ----------

const PARENT_BENEFITS = new Set([
  'nat-zasilek-macierzynski',
  'nat-urlop-macierzynski',
  'nat-urlop-rodzicielski',
  'nat-urlop-ojcowski',
  'nat-zasilek-chorobowy-ciaza',
  'nat-leki-ciaza',
  'nat-opieka-okolooporodowa',
  'nat-badania-prenatalne',
])

/**
 * Klucze osób, których dotyczy świadczenie. Świadczenia „na dziecko” przypisuje silnik (`match.child_ids`) —
 * 800+ czy stypendium trafia do każdego dziecka, którego dotyczy. Urlopy i ciąża — do zalogowanego rodzica,
 * reszta (KDR, ulga w PIT) — do całej rodziny.
 */
export function ownersOf(item: BenefitMatch, people: Person[]): string[] {
  if (item.benefit.per_child) {
    const kids = new Set(people.filter((p) => p.kind === 'child').map((p) => p.key))
    const owners = (item.match.child_ids ?? []).filter((id) => kids.has(id))
    if (owners.length) return owners
  }
  const self = people.find((p) => p.kind === 'parent')
  if (PARENT_BENEFITS.has(item.benefit.id) && self) return [self.key]
  return [FAMILY_KEY]
}

export function mattersOf(key: string, people: Person[], benefits: BenefitMatch[]): BenefitMatch[] {
  return benefits.filter((b) => b.match.status !== 'no' && ownersOf(b, people).includes(key))
}

// ---------- wskazówki ----------

export interface Guide {
  id: string
  icon: IconName
  title: string
  text: string
  /** wyróżnienie, np. zbliżający się termin */
  urgent?: string
  source?: { label: string; url: string }
}

function daysUntil(month: number, day: number, today: Date): number {
  const target = new Date(today.getFullYear(), month - 1, day)
  return Math.ceil((target.getTime() - new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime()) / 86400000)
}

export function guidesFor(person: Person, people: Person[], today = new Date()): Guide[] {
  const kids = people.filter((p) => p.kind === 'child')
  if (person.kind === 'family') {
    const out: Guide[] = [
      {
        id: 'fam-800',
        icon: 'coins',
        title: '800+ na każde dziecko',
        text: 'Wniosek o nowe dziecko złóż w ciągu 3 miesięcy od urodzenia, a świadczenie przyjdzie z wyrównaniem od dnia narodzin.',
        source: { label: 'zus.pl', url: 'https://www.zus.pl/swiadczenia/swiadczenia-wychowawcze' },
      },
      {
        id: 'fam-pit',
        icon: 'percent',
        title: 'Ulga prorodzinna w PIT',
        text: 'Odliczacie ją w rocznym zeznaniu podatkowym. Za trzecie i kolejne dziecko kwota ulgi jest wyraźnie wyższa.',
        source: { label: 'podatki.gov.pl', url: 'https://www.podatki.gov.pl/pit/ulgi-odliczenia-i-zwolnienia/ulga-na-dzieci/' },
      },
    ]
    if (kids.length >= 2) {
      out.unshift({
        id: 'fam-kdr',
        icon: 'card',
        title: 'Karta Dużej Rodziny',
        text:
          kids.length >= 3
            ? 'Po narodzinach trzeciego dziecka przysługuje Wam Karta Dużej Rodziny: zniżki na kolej, paliwo, kulturę i zakupy. Karta jest bezterminowa dla rodziców.'
            : 'Przy trzecim dziecku przysługuje Wam Karta Dużej Rodziny: zniżki na kolej, paliwo i kulturę.',
        source: { label: 'gov.pl', url: 'https://www.gov.pl/web/rodzina/karta-duzej-rodziny' },
      })
    }
    return out
  }

  if (person.kind === 'parent') {
    return [
      {
        id: 'par-one',
        icon: 'doc',
        title: 'Jeden wniosek o oba urlopy',
        text: 'Wniosek o urlop macierzyński i rodzicielski złożony do 21 dni po porodzie daje 81,5% podstawy przez cały okres, zamiast 100%, a potem 70%.',
        source: { label: 'zus.pl', url: 'https://www.zus.pl/swiadczenia/zasilki/zasilek-macierzynski' },
      },
      {
        id: 'par-41',
        icon: 'calendar',
        title: '41 tygodni urlopu rodzicielskiego',
        text: 'Dzielicie go między siebie, ale każde z Was ma 9 tygodni, których nie da się przekazać drugiemu rodzicowi.',
      },
      {
        id: 'par-protect',
        icon: 'shield',
        title: 'Ochrona pracy',
        text: 'Od ciąży do końca urlopów związanych z rodzicielstwem pracodawca co do zasady nie może wypowiedzieć ani rozwiązać umowy.',
      },
    ]
  }

  const m = person.months ?? 0
  const out: Guide[] = []
  if (person.child?.status === 'expected') {
    out.push(
      {
        id: 'kid-usc',
        icon: 'doc',
        title: 'Zgłoszenie urodzenia',
        text: 'Masz na to 21 dni od porodu. Zrobisz to w urzędzie stanu cywilnego albo online na gov.pl. Przy okazji dziecko dostanie PESEL.',
        source: { label: 'gov.pl', url: 'https://www.gov.pl/web/gov/zglos-urodzenie-dziecka' },
      },
      {
        id: 'kid-zlobek',
        icon: 'stroller',
        title: 'Zapis do żłobka',
        text: 'W Krakowie zapisy do żłobków miejskich prowadzi się elektronicznie, zwykle przez cały rok. Im wcześniej, tym lepiej.',
      },
    )
    return out
  }
  if (m < 36) {
    out.push({
      id: 'kid-zlobek',
      icon: 'stroller',
      title: 'Żłobek albo opiekunka',
      text: 'Od 12. miesiąca możecie dostać „Aktywnego rodzica”: dopłatę do żłobka albo do opieki, gdy wracacie do pracy.',
    })
    out.push({
      id: 'kid-szczepienia',
      icon: 'health',
      title: 'Szczepienia i bilanse',
      text: 'Przychodnia zaprasza na szczepienia według kalendarza i na bilanse zdrowia. Historię szczepień dziecka zobaczysz w Internetowym Koncie Pacjenta.',
      source: { label: 'pacjent.gov.pl', url: 'https://pacjent.gov.pl/internetowe-konto-pacjenta' },
    })
  } else if (m < 72) {
    out.push(
      {
        id: 'kid-przedszkole',
        icon: 'blocks',
        title: 'Rekrutacja do przedszkola',
        text: 'W Krakowie nabór do przedszkoli publicznych na kolejny rok rusza zwykle w lutym. Jeśli dziecko już chodzi do przedszkola, wcześniej składacie deklarację kontynuacji.',
        urgent: today.getMonth() >= 0 && today.getMonth() <= 2 ? 'Nabór trwa' : 'Przygotuj się na luty',
      },
      {
        id: 'kid-zerowka',
        icon: 'school',
        title: 'Obowiązkowa zerówka',
        text: 'W roku, w którym dziecko kończy 6 lat, roczne przygotowanie przedszkolne jest obowiązkowe.',
      },
    )
    if (m >= 48 && m < 60) {
      out.push({ id: 'kid-bilans', icon: 'health', title: 'Bilans 4-latka', text: 'Umów bezpłatne badanie bilansowe u pediatry.' })
    }
  } else if (m < 15 * 12) {
    const left = daysUntil(11, 30, today)
    out.push({
      id: 'kid-dobry-start',
      icon: 'backpack',
      title: 'Dobry Start: 300 zł na wyprawkę',
      text: 'Wniosek na dany rok szkolny przyjmuje ZUS od 1 lipca do 30 listopada, przez internet.',
      urgent: left >= 0 && left <= 45 ? `Zostało ${left} dni` : undefined,
      source: { label: 'zus.pl', url: 'https://www.zus.pl/swiadczenia/dobry-start' },
    })
    if (m >= 13 * 12) {
      out.push({
        id: 'kid-liceum',
        icon: 'school',
        title: 'Rekrutacja do szkoły średniej',
        text: 'W 8. klasie wybieracie szkołę ponadpodstawową. Nabór trwa zwykle od maja do lipca.',
      })
    } else {
      out.push({
        id: 'kid-swietlica',
        icon: 'clock',
        title: 'Świetlica i zajęcia',
        text: 'Zapisy do świetlicy i na zajęcia dodatkowe zwykle ruszają we wrześniu. Zapytaj w sekretariacie szkoły.',
      })
    }
  }
  if (m >= 72) {
    if (m >= 10 * 12) {
      out.push({
        id: 'kid-stypendia-wyniki',
        icon: 'target',
        title: 'Stypendia za wyniki',
        text: 'Oprócz stypendium socjalnego są stypendia za wyniki w nauce i osiągnięcia sportowe. Przyznaje je szkoła, gmina albo województwo. Zapytaj wychowawcę, które działają w waszej szkole.',
      })
    }
    out.push({
      id: 'kid-mlegitymacja',
      icon: 'card',
      title: 'Legitymacja w telefonie',
      text: 'Szkoła może wydać uczniowi mLegitymację w aplikacji mObywatel. Przydaje się przy ulgach na przejazdy i bilety. Zapytaj w sekretariacie.',
      source: { label: 'gov.pl', url: 'https://www.gov.pl/web/mobywatel/mlegitymacja-szkolna' },
    })
  }
  if (m >= 15 * 12) {
    out.push({
      id: 'kid-prm',
      icon: 'school',
      title: 'Stypendium Prezesa Rady Ministrów',
      text: 'Uczeń szkoły średniej z najlepszymi wynikami w szkole może je dostać na cały rok szkolny. Kandydata zgłasza rada pedagogiczna, warto porozmawiać z wychowawcą.',
    })
    if (m < 18 * 12) {
      out.push({
        id: 'kid-18',
        icon: 'calendar',
        title: 'Przed 18. urodzinami',
        text: '800+ przysługuje do 18. urodzin. Zasiłek rodzinny i Dobry Start mogą trwać dłużej, jeśli dziecko dalej się uczy.',
      })
    }
  }
  return out
}

export function questionsFor(person: Person): string[] {
  if (person.kind === 'family')
    return ['Ile łącznie możemy dostać w tym roku?', 'Jak dostać Kartę Dużej Rodziny?', 'Kiedy złożyć 800+ na nowe dziecko?']
  if (person.kind === 'parent')
    return [
      'Jak zaplanować urlop macierzyński i rodzicielski?',
      'Ile wyniesie mój zasiłek macierzyński?',
      'Czy mogę łączyć urlop rodzicielski z pracą?',
    ]
  if (person.child?.status === 'expected')
    return ['Co załatwić w pierwszym miesiącu po porodzie?', 'Jak zapisać maluszka do żłobka w Krakowie?']
  const m = person.months ?? 0
  if (m < 72) return [`Jak wygląda rekrutacja do przedszkola w Krakowie?`, 'Ile kosztuje przedszkole publiczne?']
  return [
    'Jak złożyć wniosek o stypendium szkolne?',
    'Jak złożyć wniosek o Dobry Start?',
    `Co przysługuje dziecku w wieku ${plYears(Math.floor(m / 12))}?`,
  ]
}
