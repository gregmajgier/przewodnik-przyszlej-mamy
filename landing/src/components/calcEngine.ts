// The landing calculator only adapts answers to the backend contract; the eligibility engine owns all calculations.

export type Role =
  | 'matka'
  | 'ojciec'
  | 'przysposabiajacy'
  | 'rodzina_zastepcza_niezawodowa'
  | 'rodzina_zastepcza_zawodowa'
export type Stage = 'ciaza' | 'urodzone' | 'adopcja_zastepcza'
export type Work =
  | 'umowa_o_prace'
  | 'umowa_zlecenia'
  | 'jdg'
  | 'wspolpraca_jdg'
  | 'ulga_na_start'
  | 'umowa_o_dzielo'
  | 'duchowny'
  | 'marynarz'
  | 'sluzba_mundurowa'
  | 'krus'
  | 'bezrobotna_z_zasilkiem'
  | 'bezrobotna_bez_zasilku'
  | 'student'
  | 'brak'
export type TriState = '' | 'tak' | 'nie'
export type AdoptionKind = 'przysposobienie' | 'rodzina_zastepcza_niezawodowa'
export type ContractKind = 'czas_nieokreslony' | 'czas_okreslony' | 'okres_probny_powyzej_1_mies' | 'okres_probny_do_1_mies' | 'zastepstwo'

export interface ChildAnswer {
  date: string
  studying: boolean
  dependent: boolean
  disabled: boolean
  inPoland: TriState
}

export interface BabyAnswer {
  weight: string
  hospitalFrom: string
  hospitalTo: string
  zaZyciem: boolean
}

export interface Answers {
  role: Role
  stage: Stage
  date: string
  childBirthDate: string
  adoptionKind: AdoptionKind
  courtDate: string
  adoptionFinalDate: string
  delayedSchool: TriState
  work: Work
  sickness: '' | 'obowiazkowe' | 'dobrowolne' | 'brak'
  insuranceStart: string
  insuranceEnd: string
  contractKind: ContractKind
  contractEnd: string
  endedInPregnancy: TriState
  payerCount: string
  incomeMode: 'average' | 'monthly'
  gross: string
  monthlyGross: string[]
  jdgDebt: string
  previousSicknessGap: string
  previousSicknessBase: string
  baseChangedInPregnancy: TriState
  changedBaseDate: string
  baseBeforeChange: string
  baseAfterChange: string
  changedConditionsInPregnancy: TriState
  changedConditionsDate: string
  pregnancyCare: TriState
  sickLeave: TriState
  sickFrom: string
  sickTo: string
  sickCodeB: TriState
  sickDaysUsed: string
  stillUnableToWork: TriState
  recoveryLikely: TriState
  exhaustionDate: string
  motherStatus: '' | 'zyje' | 'zmarla' | 'porzucila_dziecko'
  motherInsured: TriState
  childStatus: 'zywe' | 'martwe' | 'zgon_do_8_tyg' | 'zgon_po_8_tyg'
  childDeathDate: string
  babyCount: number
  pregnancyWeek: string
  babies: BabyAnswer[]
  childInPoland: TriState
  adultsInFamily: string
  familyIncomeTaxed: string
  familyIncomeUntaxed: string
  familyIncomeLost: string
  familyIncomeGained: string
  familyIncomeYear: string
  singleParent: TriState
  foreignBenefit: TriState
  alternatingCare: TriState
  otherChildren: ChildAnswer[]
  secondParentWork: Work | ''
  secondParentSickness: '' | 'obowiazkowe' | 'dobrowolne' | 'brak'
  secondParentInsuranceStart: string
  secondParentInsuranceEnd: string
  secondParentIncomeMode: 'average' | 'monthly'
  secondParentGross: string
  secondParentMonthlyGross: string[]
  secondParentPayerCount: string
  sharedHousehold: TriState
  eightOneFive: boolean
  workDuringLeave: boolean
  leaveParent: 'matka' | 'ojciec'
  leaveFrom: string
  leaveTo: string
  leaveWorkFraction: string
  city: string
  municipality: string
  county: string
  voivodeship: string
  citizenship: string
  legalStay: TriState
  ukrStatus: TriState
  ukrActive: TriState
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
  typ: string
  status: 'przysluguje' | 'nie_przysluguje' | 'brak_danych'
  instytucja: string
  przyczyny: string[]
  brakujace_zmienne: string[]
  informacje: string[]
  do_weryfikacji: boolean
  wyliczenie: {
    kwota_miesieczna: number | null
    kwota_jednorazowa: number | null
    kwota_laczna: number | null
    podstawa_wymiaru: number | null
    okresy: Period[]
    szczegoly: Record<string, unknown>
    uwagi: string[]
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
  poziom: string
  komunikat: string
  podstawa: string | null
}

export interface RequiredApplication {
  kod: string
  nazwa: string
  grupa: string
  instytucja: string
  tryb_aplikacji: string | null
  tylko_elektronicznie: boolean
  wysylka: string[]
  swiadczenia: string[]
  termin: string | null
  termin_opis: string | null
  dla: 'wnioskodawca' | 'drugi_rodzic'
}

export interface Evaluation {
  swiadczenia: Benefit[]
  swiadczenia_drugiego_rodzica: Benefit[]
  kalendarz: Deadline[]
  ryzyka: Risk[]
  wnioski: Record<string, RequiredApplication[]>
  walidacja_planu: { id: string; poziom: string; komunikat: string; data: string | null }[]
}

export interface Summary {
  granted: Benefit[]
  maybe: Benefit[]
  notGranted: Benefit[]
  secondParent: Benefit[]
  deadlines: Deadline[]
  applications: RequiredApplication[]
  risks: Risk[]
  planErrors: Evaluation['walidacja_planu']
}

export interface RequestPlan {
  profile: Record<string, unknown>
  futureProfile?: Record<string, unknown>
  futureDate?: string
}

export const SHOWN: Record<string, string> = {
  ZASILEK_CHOROBOWY_CIAZA: 'Zasiłek chorobowy w ciąży',
  ZASILEK_W_WYSOKOSCI_MACIERZYNSKIEGO: 'Zasiłek po ustaniu ubezpieczenia',
  SWIADCZENIE_REHABILITACYJNE: 'Świadczenie rehabilitacyjne',
  ZASILEK_MACIERZYNSKI_MATKA: 'Zasiłek macierzyński',
  ZASILEK_MACIERZYNSKI_OJCIEC_PRZEJECIE: 'Zasiłek macierzyński — przejęcie przez ojca',
  ZASILEK_MACIERZYNSKI_MARTWE_URODZENIE: 'Zasiłek po martwym urodzeniu lub śmierci dziecka',
  ZASILEK_URLOP_RODZICIELSKI: 'Zasiłek za urlop rodzicielski',
  ZASILEK_URLOP_OJCOWSKI: 'Zasiłek za urlop ojcowski',
  ZASILEK_URLOP_UZUPELNIAJACY: 'Zasiłek za uzupełniający urlop macierzyński',
  ZASILEK_ADOPCJA_ZASTEPCZA: 'Zasiłek po przyjęciu dziecka na wychowanie',
  ZASILEK_POGRZEBOWY: 'Zasiłek pogrzebowy',
  SWIADCZENIE_RODZICIELSKIE: 'Świadczenie rodzicielskie',
  ZASILEK_800PLUS: '800+',
  BECIKOWE: 'Becikowe',
  ZASILEK_RODZINNY: 'Zasiłek rodzinny',
  ZA_ZYCIEM_4000: 'Za życiem',
  AKTYWNY_RODZIC: 'Aktywny rodzic',
}

const pad = (n: number) => String(n).padStart(2, '0')
export const isoDate = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
export const parseDate = (s: string) => {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, m - 1, d)
}
const addDays = (d: Date, days: number) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + days)
const isValidDate = (s: string) => /^\d{4}-\d{2}-\d{2}$/.test(s) && isoDate(parseDate(s)) === s
const moneyValue = (s: string) => Number(s.trim().replace(/\s/g, '').replace(',', '.'))

export function defaultDueDate(today = new Date()): string {
  return isoDate(new Date(today.getFullYear(), today.getMonth() + 4, today.getDate()))
}

export const VOLUNTARY: Work[] = ['umowa_zlecenia', 'jdg', 'wspolpraca_jdg', 'ulga_na_start']
export const INSURED: Work[] = ['umowa_o_prace', ...VOLUNTARY, 'duchowny', 'marynarz', 'sluzba_mundurowa']
export const needsPay = (a: Answers) =>
  INSURED.includes(a.work) &&
  (a.work === 'umowa_o_prace' || a.sickness === 'obowiazkowe' || a.sickness === 'dobrowolne')

/** Polish error message for the form, or null when the answers can be sent. */
export function validate(a: Answers, today = new Date()): string | null {
  if (!isValidDate(a.date)) {
    if (a.stage === 'ciaza') return 'Podaj prawidłowy przewidywany termin porodu.'
    if (a.stage === 'adopcja_zastepcza') return 'Podaj prawidłową datę przyjęcia dziecka na wychowanie.'
    return 'Podaj prawidłową datę urodzenia dziecka.'
  }
  const d = parseDate(a.date)
  const t = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  if (a.stage === 'ciaza' && (d < t || d > addDays(t, 300))) return 'Termin porodu powinien przypadać w ciągu najbliższych 10 miesięcy.'
  if (a.stage === 'urodzone' && (d > t || d < new Date(t.getFullYear() - 18, t.getMonth(), t.getDate())))
    return 'Podaj datę urodzenia z ostatnich 18 lat.'
  if (a.stage === 'adopcja_zastepcza') {
    if (!isValidDate(a.childBirthDate)) return 'Podaj datę urodzenia dziecka przyjętego na wychowanie.'
    if (parseDate(a.childBirthDate) > d) return 'Data urodzenia dziecka nie może być późniejsza niż data przyjęcia.'
    if (a.courtDate && !isValidDate(a.courtDate)) return 'Sprawdź datę wystąpienia do sądu.'
    if (a.adoptionFinalDate && !isValidDate(a.adoptionFinalDate)) return 'Sprawdź datę uprawomocnienia orzeczenia.'
  }
  if (a.insuranceStart && (!isValidDate(a.insuranceStart) || parseDate(a.insuranceStart) > t))
    return 'Sprawdź datę objęcia ubezpieczeniem chorobowym.'
  if (a.insuranceEnd && (!isValidDate(a.insuranceEnd) || (a.insuranceStart && parseDate(a.insuranceEnd) < parseDate(a.insuranceStart))))
    return 'Data ustania ubezpieczenia nie może poprzedzać daty jego rozpoczęcia.'
  if (a.secondParentWork && a.secondParentInsuranceStart && (!isValidDate(a.secondParentInsuranceStart) || parseDate(a.secondParentInsuranceStart) > t))
    return 'Sprawdź datę objęcia ubezpieczeniem drugiego rodzica.'
  if (a.secondParentInsuranceEnd && (!isValidDate(a.secondParentInsuranceEnd) || (a.secondParentInsuranceStart && parseDate(a.secondParentInsuranceEnd) < parseDate(a.secondParentInsuranceStart))))
    return 'Data ustania ubezpieczenia drugiego rodzica nie może poprzedzać daty rozpoczęcia.'
  if (a.secondParentPayerCount && (!Number.isInteger(Number(a.secondParentPayerCount)) || Number(a.secondParentPayerCount) < 0))
    return 'Liczba osób zgłoszonych do ubezpieczenia przez płatnika drugiego rodzica nie może być ujemna.'
  if (a.contractEnd && !isValidDate(a.contractEnd)) return 'Sprawdź datę końca umowy.'
  if (a.payerCount && (!Number.isInteger(Number(a.payerCount)) || Number(a.payerCount) < 0))
    return 'Liczba osób zgłoszonych do ubezpieczenia przez płatnika nie może być ujemna.'

  const incomeValues = a.incomeMode === 'average' ? [a.gross] : a.monthlyGross.filter(Boolean)
  for (const value of incomeValues) {
    const n = moneyValue(value)
    if (!Number.isFinite(n) || n < 0 || n > 1_000_000) return 'Podstawa składek musi być kwotą od 0 do 1 000 000 zł.'
  }
  const secondParentIncomeValues =
    a.secondParentIncomeMode === 'average' ? [a.secondParentGross] : a.secondParentMonthlyGross.filter(Boolean)
  for (const value of secondParentIncomeValues) {
    const n = moneyValue(value)
    if (!Number.isFinite(n) || n < 0 || n > 1_000_000) return 'Podstawa składek drugiego rodzica musi być kwotą od 0 do 1 000 000 zł.'
  }
  for (const value of [a.jdgDebt, a.previousSicknessBase, a.baseBeforeChange, a.baseAfterChange]) {
    if (value && (!Number.isFinite(moneyValue(value)) || moneyValue(value) < 0))
      return 'Sprawdź podaną kwotę — powinna być nieujemną liczbą.'
  }
  if (a.previousSicknessGap && (!Number.isInteger(Number(a.previousSicknessGap)) || Number(a.previousSicknessGap) < 0))
    return 'Przerwa od poprzedniego zasiłku podaj w pełnych dniach.'
  if (a.changedBaseDate && !isValidDate(a.changedBaseDate)) return 'Sprawdź datę zmiany podstawy składek.'
  if (a.changedConditionsDate && !isValidDate(a.changedConditionsDate)) return 'Sprawdź datę zmiany warunków zatrudnienia.'
  if (a.sickFrom && !isValidDate(a.sickFrom)) return 'Sprawdź początek e-ZLA.'
  if (a.sickTo && !isValidDate(a.sickTo)) return 'Sprawdź koniec e-ZLA.'
  if (a.sickLeave === 'tak' && !a.sickFrom) return 'Podaj początek e-ZLA, jeśli chcesz uwzględnić zwolnienie.'
  if (a.sickFrom && a.sickTo && parseDate(a.sickTo) < parseDate(a.sickFrom)) return 'Koniec e-ZLA nie może być wcześniejszy niż jego początek.'
  if (a.sickDaysUsed && (!Number.isInteger(Number(a.sickDaysUsed)) || Number(a.sickDaysUsed) < 0))
    return 'Wykorzystany okres zasiłkowy podaj w pełnych dniach.'
  if (a.exhaustionDate && !isValidDate(a.exhaustionDate)) return 'Sprawdź datę wyczerpania okresu zasiłkowego.'
  if (a.childDeathDate && !isValidDate(a.childDeathDate)) return 'Sprawdź datę śmierci dziecka.'
  if (a.stage === 'urodzone' && a.childStatus.startsWith('zgon_') && !a.childDeathDate)
    return 'Podaj datę śmierci dziecka, aby dobrać właściwy okres świadczenia.'
  if (a.pregnancyWeek && (!Number.isInteger(Number(a.pregnancyWeek)) || Number(a.pregnancyWeek) < 20 || Number(a.pregnancyWeek) > 45))
    return 'Tydzień ciąży podaj jako liczbę od 20 do 45.'

  if (!Number.isInteger(a.babyCount) || a.babyCount < 1 || a.babyCount > 10) return 'Liczba dzieci z porodu powinna wynosić od 1 do 10.'
  if (!Number.isInteger(Number(a.adultsInFamily)) || Number(a.adultsInFamily) < 1 || Number(a.adultsInFamily) > 10)
    return 'Podaj liczbę dorosłych osób we wspólnym gospodarstwie (od 1 do 10).'
  if (a.familyIncomeYear && (!/^\d{4}$/.test(a.familyIncomeYear) || Number(a.familyIncomeYear) > t.getFullYear()))
    return 'Podaj prawidłowy rok bazowy dochodu.'
  if ([a.familyIncomeTaxed, a.familyIncomeUntaxed, a.familyIncomeLost, a.familyIncomeGained].some(Boolean) && !a.familyIncomeYear)
    return 'Podaj rok, którego dotyczą wpisane dochody.'
  for (const value of [a.familyIncomeTaxed, a.familyIncomeUntaxed, a.familyIncomeLost, a.familyIncomeGained]) {
    if (value && (!Number.isFinite(moneyValue(value)) || moneyValue(value) < 0 || moneyValue(value) > 100_000_000))
      return 'Roczny dochód podaj jako kwotę od 0 do 100 000 000 zł.'
  }
  for (const child of [...a.otherChildren, ...a.babies]) {
    if ('date' in child && child.date && !isValidDate(child.date)) return 'Sprawdź datę urodzenia jednego z dzieci.'
    if ('weight' in child && child.weight && (!Number.isInteger(Number(child.weight)) || Number(child.weight) < 200 || Number(child.weight) > 7000))
      return 'Masa urodzeniowa powinna mieścić się w zakresie 200–7000 g.'
    if ('hospitalFrom' in child && child.hospitalFrom && !isValidDate(child.hospitalFrom)) return 'Sprawdź początek pobytu dziecka w szpitalu.'
    if ('hospitalTo' in child && child.hospitalTo && !isValidDate(child.hospitalTo)) return 'Sprawdź koniec pobytu dziecka w szpitalu.'
    if ('hospitalFrom' in child && child.hospitalFrom && child.hospitalTo && parseDate(child.hospitalTo) < parseDate(child.hospitalFrom))
      return 'Koniec hospitalizacji nie może być wcześniejszy niż jej początek.'
  }
  if (a.workDuringLeave) {
    if (!isValidDate(a.leaveFrom) || !isValidDate(a.leaveTo) || parseDate(a.leaveTo) < parseDate(a.leaveFrom))
      return 'Podaj prawidłowe daty planowanej części urlopu rodzicielskiego.'
    if (!Number.isFinite(Number(a.leaveWorkFraction)) || Number(a.leaveWorkFraction) <= 0 || Number(a.leaveWorkFraction) > 0.5)
      return 'Praca w czasie urlopu rodzicielskiego może wynosić maksymalnie 1/2 etatu.'
  }
  return null
}

function lastTwelveMonths(ref: Date): { rok: number; miesiac: number }[] {
  const out = []
  for (let i = 12; i >= 1; i--) {
    const d = new Date(ref.getFullYear(), ref.getMonth() - i, 1)
    out.push({ rok: d.getFullYear(), miesiac: d.getMonth() + 1 })
  }
  return out
}

function boolOrNull(v: TriState): boolean | null {
  return v === '' ? null : v === 'tak'
}

function incomeRows(a: Answers, months: { rok: number; miesiac: number }[]) {
  if (!needsPay(a)) return []
  if (a.incomeMode === 'average') {
    if (!a.gross.trim()) return []
    const value = moneyValue(a.gross)
    return months.map((m) => ({ ...m, value }))
  }
  return months.flatMap((m, i) => {
    const entry = a.monthlyGross[i]
    return entry?.trim() ? [{ ...m, value: moneyValue(entry) }] : []
  })
}

export function buildRequest(a: Answers): RequestPlan {
  const referenceDate = parseDate(a.date)
  const months = lastTwelveMonths(referenceDate)
  const rows = incomeRows(a, months)
  const chorobowe =
    a.work === 'umowa_o_prace'
      ? 'obowiazkowe'
      : INSURED.includes(a.work)
        ? a.sickness || null
        : 'brak'
  const ubezpieczenie: Record<string, unknown> = { tytul: a.work, chorobowe }

  if (chorobowe !== 'brak' && a.insuranceStart) ubezpieczenie.data_objecia_chorobowym = a.insuranceStart
  if (a.insuranceEnd) ubezpieczenie.data_ustania = a.insuranceEnd
  if (a.work === 'umowa_o_prace') {
    ubezpieczenie.rodzaj_umowy_o_prace = a.contractKind
    if (a.contractEnd) ubezpieczenie.data_konca_umowy = a.contractEnd
    ubezpieczenie.umowa_rozwiazana_w_ciazy = boolOrNull(a.endedInPregnancy)
  }
  if (a.payerCount) ubezpieczenie.platnik = { liczba_ubezpieczonych_chorobowo: Number(a.payerCount) }
  if (rows.length) {
    if (a.work === 'jdg' || a.work === 'wspolpraca_jdg' || a.work === 'duchowny') {
      ubezpieczenie.zadeklarowana_podstawa_jdg = rows.map(({ value, ...m }) => ({ ...m, kwota: value }))
    } else {
      ubezpieczenie.przychody_12_miesiecy = rows.map(({ value, ...m }) => ({ ...m, podstawa_wymiaru_skladek: value }))
    }
  }
  if (a.jdgDebt) ubezpieczenie.zadluzenie_skladkowe = { kwota: moneyValue(a.jdgDebt), na_dzien: a.date }
  if (a.previousSicknessGap) ubezpieczenie.przerwa_od_poprzedniego_zasilku_dni = Number(a.previousSicknessGap)
  if (a.previousSicknessBase) ubezpieczenie.podstawa_poprzedniego_zasilku = moneyValue(a.previousSicknessBase)
  if (a.baseChangedInPregnancy !== '') {
    ubezpieczenie.zmiana_podstawy_w_ciazy = {
      czy: a.baseChangedInPregnancy === 'tak',
      data: a.changedBaseDate || null,
      kwota_przed: a.baseBeforeChange ? moneyValue(a.baseBeforeChange) : null,
      kwota_po: a.baseAfterChange ? moneyValue(a.baseAfterChange) : null,
    }
  }
  if (a.changedConditionsInPregnancy !== '') {
    ubezpieczenie.zmiana_warunkow_zatrudnienia_w_ciazy = {
      czy: a.changedConditionsInPregnancy === 'tak',
      data: a.changedConditionsDate || null,
      opis: 'Zmiana warunków zatrudnienia w ciąży zgłoszona w kalkulatorze',
    }
  }

  let secondParentInsurance: Record<string, unknown> | undefined
  if (a.secondParentWork) {
    const secondParentAnswers: Answers = {
      ...a,
      work: a.secondParentWork,
      sickness: a.secondParentSickness,
      gross: a.secondParentGross,
      monthlyGross: a.secondParentMonthlyGross,
      incomeMode: a.secondParentIncomeMode,
    }
    const partnerRows = incomeRows(secondParentAnswers, months)
    const partnerSickness =
      a.secondParentWork === 'umowa_o_prace'
        ? 'obowiazkowe'
        : INSURED.includes(a.secondParentWork)
          ? a.secondParentSickness || null
          : 'brak'
    secondParentInsurance = { tytul: a.secondParentWork, chorobowe: partnerSickness }
    if (partnerSickness !== 'brak' && a.secondParentInsuranceStart)
      secondParentInsurance.data_objecia_chorobowym = a.secondParentInsuranceStart
    if (a.secondParentInsuranceEnd) secondParentInsurance.data_ustania = a.secondParentInsuranceEnd
    if (a.secondParentPayerCount)
      secondParentInsurance.platnik = { liczba_ubezpieczonych_chorobowo: Number(a.secondParentPayerCount) }
    if (partnerRows.length) {
      if (a.secondParentWork === 'jdg' || a.secondParentWork === 'wspolpraca_jdg' || a.secondParentWork === 'duchowny') {
        secondParentInsurance.zadeklarowana_podstawa_jdg = partnerRows.map(({ value, ...m }) => ({ ...m, kwota: value }))
      } else {
        secondParentInsurance.przychody_12_miesiecy = partnerRows.map(({ value, ...m }) => ({ ...m, podstawa_wymiaru_skladek: value }))
      }
    }
  }

  const children: Record<string, unknown>[] = a.otherChildren.map((child) => ({
    data_urodzenia: child.date || null,
    pobyt_w_polsce: boolOrNull(child.inPoland),
    uczy_sie: child.studying,
    na_utrzymaniu: child.dependent,
    ...(child.disabled ? { niepelnosprawnosc: { orzeczenie: 'tak' } } : {}),
  }))

  if (a.stage === 'adopcja_zastepcza') {
    children.push({
      data_urodzenia: a.childBirthDate,
      pobyt_w_polsce: boolOrNull(a.childInPoland),
      na_utrzymaniu: true,
      odroczony_obowiazek_szkolny: boolOrNull(a.delayedSchool),
      przyjete_na_wychowanie: {
        rodzaj: a.adoptionKind,
        data_przyjecia: a.date,
        ...(a.courtDate ? { data_wystapienia_do_sadu: a.courtDate } : {}),
        ...(a.adoptionFinalDate ? { data_uprawomocnienia: a.adoptionFinalDate } : {}),
      },
    })
  } else {
    for (let i = 0; i < a.babyCount; i++) {
      const baby = a.babies[i] ?? { weight: '', hospitalFrom: '', hospitalTo: '', zaZyciem: false }
      const hospital = baby.hospitalFrom && baby.hospitalTo ? [{ od: baby.hospitalFrom, do: baby.hospitalTo }] : []
      children.push({
        data_urodzenia: a.date,
        pobyt_w_polsce: boolOrNull(a.childInPoland),
        na_utrzymaniu: true,
        zaswiadczenie_za_zyciem: baby.zaZyciem,
        ...(baby.weight ? { masa_urodzeniowa_g: Number(baby.weight) } : {}),
        hospitalizacja: hospital,
      })
    }
  }

  const familySize = Number(a.adultsInFamily) + children.length
  const family: Record<string, unknown> = {
    sklad: Array.from({ length: familySize }, (_, i) => ({ imie: `Osoba ${i + 1}` })),
    samotne_wychowywanie: boolOrNull(a.singleParent),
    wspolne_gospodarstwo_domowe: boolOrNull(a.sharedHousehold),
    opieka_naprzemienna: boolOrNull(a.alternatingCare),
    swiadczenie_za_granica: boolOrNull(a.foreignBenefit),
    inne_pobierane_swiadczenia: [],
  }
  const incomeFields = [a.familyIncomeTaxed, a.familyIncomeUntaxed, a.familyIncomeLost, a.familyIncomeGained]
  if (incomeFields.some(Boolean)) {
    family.dochod_rok_bazowy = {
      rok: Number(a.familyIncomeYear),
      dochody_opodatkowane: a.familyIncomeTaxed ? moneyValue(a.familyIncomeTaxed) : 0,
      dochody_nieopodatkowane: a.familyIncomeUntaxed ? moneyValue(a.familyIncomeUntaxed) : 0,
      dochody_utracone: a.familyIncomeLost ? moneyValue(a.familyIncomeLost) : 0,
      dochody_uzyskane: a.familyIncomeGained ? moneyValue(a.familyIncomeGained) : 0,
    }
  }

  const role = a.stage === 'adopcja_zastepcza' ? a.role : a.role
  const profile: Record<string, unknown> = {
    wnioskodawca: {
      etap: a.stage === 'ciaza' ? 'w_ciazy' : a.stage,
      rola: role,
      obywatelstwo: a.citizenship || 'PL',
      legalny_pobyt_w_polsce: boolOrNull(a.legalStay),
      status_ukr: boolOrNull(a.ukrStatus),
      aktywnosc_zawodowa_ukr: boolOrNull(a.ukrActive),
      adres_zamieszkania: {
        kraj: 'PL',
        ...(a.city.trim() ? { miejscowosc: a.city.trim() } : {}),
        ...(a.municipality.trim() ? { gmina: a.municipality.trim() } : {}),
        ...(a.county.trim() ? { powiat: a.county.trim() } : {}),
        ...(a.voivodeship.trim() ? { wojewodztwo: a.voivodeship.trim() } : {}),
      },
    },
    ciaza: {
      w_ciazy: a.stage === 'ciaza',
      ...(a.stage === 'ciaza' ? { przewidywana_data_porodu: a.date } : {}),
      opieka_medyczna_od_10_tyg: boolOrNull(a.pregnancyCare),
    },
    porod:
      a.stage === 'adopcja_zastepcza'
        ? { stan_dziecka: null, liczba_dzieci: null }
        : {
            data_porodu: a.date,
            liczba_dzieci: a.babyCount,
            stan_dziecka: a.stage === 'ciaza' ? 'zywe' : a.childStatus,
            ...(a.stage === 'urodzone' && a.childDeathDate ? { data_zgonu_dziecka: a.childDeathDate } : {}),
            ...(a.pregnancyWeek ? { tydzien_ciazy: Number(a.pregnancyWeek) } : {}),
          },
    dzieci: children,
    matka: {
      ...(a.motherStatus ? { stan: a.motherStatus } : {}),
      ubezpieczona_w_dniu_porodu: boolOrNull(a.motherInsured),
    },
    drugi_rodzic: {
      ...(a.secondParentWork
        ? { tytul_ubezpieczenia: a.secondParentWork, ubezpieczenie: secondParentInsurance }
        : {}),
    },
    zdrowie: {
      ezla:
        a.sickLeave === ''
          ? null
          : a.sickLeave === 'tak'
            ? a.sickFrom
              ? [{ od: a.sickFrom, do: a.sickTo || a.sickFrom, kod_B: boolOrNull(a.sickCodeB) }]
              : null
            : [],
      ...(a.sickDaysUsed ? { okres_zasilkowy_wykorzystany_dni: Number(a.sickDaysUsed) } : {}),
      ...(a.stillUnableToWork ? { nadal_niezdolna_do_pracy: boolOrNull(a.stillUnableToWork) } : {}),
      ...(a.recoveryLikely ? { rokowania_odzyskania_zdolnosci: boolOrNull(a.recoveryLikely) } : {}),
      ...(a.exhaustionDate ? { data_wyczerpania_zasilku: a.exhaustionDate } : {}),
    },
    rodzina: family,
    ubezpieczenie,
  }

  const plan: Record<string, unknown> = {}
  if (a.eightOneFive) plan.wniosek_81_5 = { czy: true, data_zlozenia: a.stage === 'urodzone' ? isoDate(new Date()) : a.date }
  if (a.workDuringLeave) {
    plan.czesci_urlopu_rodzicielskiego = [
      {
        rodzic: a.leaveParent,
        od: a.leaveFrom,
        do: a.leaveTo,
        wymiar_pracy_w_trakcie: Number(a.leaveWorkFraction),
      },
    ]
  }
  if (Object.keys(plan).length) profile.plan = plan

  if (a.stage !== 'ciaza') return { profile }
  return {
    profile,
    futureProfile: {
      ...profile,
      wnioskodawca: { ...(profile.wnioskodawca as Record<string, unknown>), etap: 'po_porodzie' },
    },
    futureDate: a.date,
  }
}

const ORDER = Object.keys(SHOWN)
const byOrder = (x: Benefit, y: Benefit) => ORDER.indexOf(x.id) - ORDER.indexOf(y.id)

export function summarize(e: Evaluation): Summary {
  const shown = e.swiadczenia.filter((b) => b.id in SHOWN).sort(byOrder)
  const hasAmount = (b: Benefit) =>
    b.wyliczenie !== null && (b.wyliczenie.kwota_miesieczna !== null || b.wyliczenie.kwota_jednorazowa !== null)
  const applications = Object.values(e.wnioski).flat().filter(
    (application, index, all) => all.findIndex((other) => other.kod === application.kod && other.dla === application.dla) === index,
  )
  return {
    granted: shown.filter((b) => b.status === 'przysluguje' && hasAmount(b)),
    maybe: shown.filter((b) => b.status === 'brak_danych' || (b.status === 'przysluguje' && !hasAmount(b))),
    notGranted: shown.filter((b) => b.status === 'nie_przysluguje'),
    secondParent: e.swiadczenia_drugiego_rodzica.filter((b) => b.id in SHOWN).sort(byOrder),
    deadlines: e.kalendarz.filter((d) => d.rodzaj !== 'plan').sort((x, y) => x.data.localeCompare(y.data)).slice(0, 8),
    applications,
    risks: e.ryzyka,
    planErrors: e.walidacja_planu,
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
