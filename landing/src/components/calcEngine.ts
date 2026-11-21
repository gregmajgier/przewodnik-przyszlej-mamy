// Landing calculator logic: builds an engine profile (backend/app/engine/schemas.py, contract v1.1) from a few
// answers and picks what to show from POST /api/silnik/ocena. Eligibility and amounts come only from
// the engine; this file never computes money itself.

export type Role = 'matka' | 'ojciec'
export type Stage = 'ciaza' | 'urodzone'
export type Work = 'umowa_o_prace' | 'umowa_zlecenia' | 'jdg' | 'student' | 'brak'
export type Tenure = 'ponad_rok' | 'od_3_mies' | 'krocej'

export interface Answers {
  role: Role
  stage: Stage
  date: string // YYYY-MM-DD: due date or birth date
  work: Work
  sickness: boolean // voluntary sickness insurance (zlecenie / JDG)
  tenure: Tenure
  gross: string // monthly gross pay or JDG declared base, zł
  familyIncome: string // optional: family's yearly net income, zł
  familySize: string // optional: people in the family including the baby
}

export interface Period {
  nazwa: string
  od: string | null
  do: string | null
  tygodnie: number | null
  procent: number | null
  kwota: number | null
  wyplaca: string | null
}

export interface Benefit {
  id: string
  nazwa: string
  status: 'przysluguje' | 'nie_przysluguje' | 'brak_danych'
  instytucja: string
  wyliczenie: {
    kwota_miesieczna: number | null
    kwota_jednorazowa: number | null
    kwota_laczna: number | null
    okresy: Period[]
    szczegoly: Record<string, unknown>
    brakujace_dane: string[]
  } | null
}

export interface Deadline {
  data: string
  rodzaj: string
  opis: string
  swiadczenie: string | null
}

export interface Risk {
  id: string
  nazwa: string
  komunikat: string
}

export interface Evaluation {
  swiadczenia: Benefit[]
  kalendarz: Deadline[]
  ryzyka: Risk[]
}

/** Money benefits worth showing on the landing, in display order, with short names. */
export const SHOWN: Record<string, { name: string; note?: string }> = {
  ZASILEK_MACIERZYNSKI_MATKA: { name: 'Zasiłek macierzyński' },
  ZASILEK_URLOP_RODZICIELSKI: { name: 'Zasiłek za urlop rodzicielski' },
  ZASILEK_URLOP_OJCOWSKI: { name: 'Zasiłek za urlop ojcowski' },
  SWIADCZENIE_RODZICIELSKIE: { name: 'Świadczenie rodzicielskie', note: 'Dla rodziców bez zasiłku macierzyńskiego.' },
  ZASILEK_800PLUS: { name: '800+', note: 'Co miesiąc, do 18. urodzin dziecka.' },
  BECIKOWE: { name: 'Becikowe', note: 'Jednorazowo z gminy, zależy od dochodu rodziny.' },
  ZASILEK_RODZINNY: { name: 'Zasiłek rodzinny' },
  ZA_ZYCIEM_4000: { name: 'Za życiem' },
  AKTYWNY_RODZIC: { name: 'Aktywny rodzic' },
}

const pad = (n: number) => String(n).padStart(2, '0')
export const isoDate = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
export const parseDate = (s: string) => {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, m - 1, d)
}
const addDays = (d: Date, days: number) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + days)

export function defaultDueDate(today = new Date()): string {
  return isoDate(new Date(today.getFullYear(), today.getMonth() + 4, today.getDate()))
}

export const INSURED: Work[] = ['umowa_o_prace', 'umowa_zlecenia', 'jdg']
export const needsPay = (a: Answers) => INSURED.includes(a.work) && (a.work === 'umowa_o_prace' || a.sickness)

const TENURE_DAYS: Record<Tenure, number> = { ponad_rok: 400, od_3_mies: 150, krocej: 45 }

/** Polish error message for the form, or null when the answers can be sent. */
export function validate(a: Answers, today = new Date()): string | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(a.date)) return a.stage === 'ciaza' ? 'Podaj termin porodu.' : 'Podaj datę urodzenia dziecka.'
  const d = parseDate(a.date)
  const t = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  if (a.stage === 'ciaza' && (d < t || d > addDays(t, 300))) return 'Termin porodu powinien przypadać w ciągu najbliższych 10 miesięcy.'
  if (a.stage === 'urodzone' && (d > t || d < addDays(t, -3 * 365))) return 'Kalkulator liczy dla dzieci do 3 lat. Podaj datę urodzenia z tego okresu.'
  if (needsPay(a)) {
    const g = Number(a.gross.replace(',', '.'))
    if (!a.gross.trim() || !Number.isFinite(g) || g <= 0 || g > 100000) return 'Podaj miesięczną kwotę brutto, na przykład 7000.'
  }
  const hasIncome = a.familyIncome.trim() !== ''
  const hasSize = a.familySize.trim() !== ''
  if (hasIncome !== hasSize) return 'Do dochodu rodziny podaj też liczbę osób w rodzinie (albo zostaw oba pola puste).'
  if (hasIncome) {
    const inc = Number(a.familyIncome.replace(',', '.'))
    const size = Number(a.familySize)
    if (!Number.isFinite(inc) || inc < 0 || inc > 10_000_000) return 'Dochód rodziny podaj w złotych, na przykład 60000.'
    if (!Number.isInteger(size) || size < 2 || size > 15) return 'Liczba osób w rodzinie to od 2 do 15 (razem z dzieckiem).'
  }
  return null
}

/** Last 12 full months before the birth month: the base period for ZUS benefits. */
function lastTwelveMonths(ref: Date): { rok: number; miesiac: number }[] {
  const out = []
  for (let i = 12; i >= 1; i--) {
    const d = new Date(ref.getFullYear(), ref.getMonth() - i, 1)
    out.push({ rok: d.getFullYear(), miesiac: d.getMonth() + 1 })
  }
  return out
}

/**
 * Request for the engine. For a pregnancy we evaluate the situation on the due date (`data_oceny`),
 * so the result shows the leave, 800+ and becikowe that start after the birth.
 */
export function buildRequest(a: Answers): { profile: Record<string, unknown>; dataOceny: string | null } {
  const birth = parseDate(a.date)
  const gross = Number(a.gross.replace(',', '.'))
  const insured = INSURED.includes(a.work)
  const chorobowe = a.work === 'umowa_o_prace' ? 'obowiazkowe' : insured && a.sickness ? 'dobrowolne' : 'brak'
  const months = lastTwelveMonths(birth)

  const ubezpieczenie: Record<string, unknown> = { tytul: a.work, chorobowe }
  if (chorobowe !== 'brak') {
    ubezpieczenie.data_objecia_chorobowym = isoDate(addDays(birth, -TENURE_DAYS[a.tenure]))
    if (a.work === 'jdg') ubezpieczenie.zadeklarowana_podstawa_jdg = months.map((m) => ({ ...m, kwota: gross }))
    else ubezpieczenie.przychody_12_miesiecy = months.map((m) => ({ ...m, podstawa_wymiaru_skladek: gross }))
  }

  const rodzina: Record<string, unknown> = { swiadczenie_za_granica: false, inne_pobierane_swiadczenia: [] }
  if (a.familyIncome.trim() && a.familySize.trim()) {
    rodzina.sklad = Array.from({ length: Number(a.familySize) }, (_, i) => ({ imie: `Osoba ${i + 1}` }))
    rodzina.dochod_rok_bazowy = {
      rok: birth.getFullYear() - 1,
      dochody_opodatkowane: Number(a.familyIncome.replace(',', '.')),
      dochody_nieopodatkowane: 0,
      dochody_utracone: 0,
      dochody_uzyskane: 0,
    }
  }

  const profile = {
    wnioskodawca: {
      etap: 'po_porodzie',
      rola: a.role,
      obywatelstwo: 'PL',
      legalny_pobyt_w_polsce: true,
      status_ukr: false,
      adres_zamieszkania: { kraj: 'PL' },
    },
    ciaza: { opieka_medyczna_od_10_tyg: true },
    porod: { data_porodu: a.date, liczba_dzieci: 1, stan_dziecka: 'zywe' },
    dzieci: [{ data_urodzenia: a.date, pobyt_w_polsce: true }],
    matka: { stan: 'zyje' },
    zdrowie: { ezla: [], okres_zasilkowy_wykorzystany_dni: 0, zasilek_opiekunczy_wykorzystany_dni: 0 },
    rodzina,
    ubezpieczenie,
  }
  return { profile, dataOceny: a.stage === 'ciaza' ? a.date : null }
}

export interface Summary {
  granted: Benefit[]
  maybe: Benefit[]
  deadlines: Deadline[]
  risks: Risk[]
}

const ORDER = Object.keys(SHOWN)
const byOrder = (x: Benefit, y: Benefit) => ORDER.indexOf(x.id) - ORDER.indexOf(y.id)

export function summarize(e: Evaluation): Summary {
  const shown = e.swiadczenia.filter((b) => b.id in SHOWN)
  const hasAmount = (b: Benefit) =>
    b.wyliczenie !== null && (b.wyliczenie.kwota_miesieczna !== null || b.wyliczenie.kwota_jednorazowa !== null)
  return {
    granted: shown.filter((b) => b.status === 'przysluguje' && hasAmount(b)).sort(byOrder),
    maybe: shown.filter((b) => b.status === 'brak_danych' || (b.status === 'przysluguje' && !hasAmount(b))).sort(byOrder),
    deadlines: e.kalendarz
      .filter((d) => d.rodzaj === 'zlozenie_wniosku' || d.rodzaj === 'ostrzezenie')
      // the engine may list one deadline twice (e.g. 81.5% and the joint leave form): keep one per date and benefit
      .filter((d, i, all) => all.findIndex((x) => x.data === d.data && x.swiadczenie === d.swiadczenie) === i)
      .sort((x, y) => x.data.localeCompare(y.data))
      .slice(0, 4),
    risks: e.ryzyka,
  }
}

const money = new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN', maximumFractionDigits: 0 })
export const zl = (n: number) => money.format(Math.round(n))
export const plDate = (s: string) => parseDate(s).toLocaleDateString('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' })

/** 81.5% vs 100% + 70% comparison for maternity, if the engine returned both variants. */
export function maternityVariants(b: Benefit): { even: number; split: [number, number] } | null {
  const s = b.wyliczenie?.szczegoly as
    | { wariant_81_5?: { kwota_miesieczna?: number }; wariant_100_70?: { macierzynski_miesiecznie?: number; rodzicielski_miesiecznie?: number } }
    | undefined
  const even = s?.wariant_81_5?.kwota_miesieczna
  const hi = s?.wariant_100_70?.macierzynski_miesiecznie
  const lo = s?.wariant_100_70?.rodzicielski_miesiecznie
  return even && hi && lo ? { even, split: [hi, lo] } : null
}
