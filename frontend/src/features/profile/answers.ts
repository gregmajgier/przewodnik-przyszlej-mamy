// Odpowiedzi rodzica zapisane w profilu (`answers`) — ludzkie etykiety zamiast kluczy technicznych.

/** klucz odpowiedzi `benefit:<id>:<warunek>` → treść pytania z katalogu świadczeń */
export type QuestionTexts = Record<string, string>

/** Dane do wniosków (z formularzy) — klucze z `source_key: "answers.*"` w mapach pól. */
const FORM_LABELS: Record<string, string> = {
  street: 'Ulica',
  house_no: 'Numer domu',
  flat_no: 'Numer lokalu',
  phone: 'Telefon',
  account_number: 'Numer konta',
  employer_email: 'E-mail do kadr',
  za_zyciem_certificate: 'Zaświadczenie „Za życiem”',
}

const INCOME_PREFIX = 'income_le:'
const BENEFIT_PREFIX = 'benefit:'

export function isApplicationAnswer(key: string, value: unknown): boolean {
  return key in FORM_LABELS && typeof value === 'string'
}

export function needsBenefitNames(answers: Record<string, unknown>): boolean {
  return Object.keys(answers).some((k) => k.startsWith(BENEFIT_PREFIX))
}

interface CatalogEntry {
  benefit: { id: string; name: string; extra_conditions?: { id: string; text: string; question?: string | null }[] }
}

/** Treści pytań z katalogu (`/api/benefits`), także odpowiedzi o dochód przy konkretnym świadczeniu. */
export function questionTexts(all: CatalogEntry[]): QuestionTexts {
  const texts: QuestionTexts = {}
  for (const { benefit } of all) {
    texts[`${BENEFIT_PREFIX}${benefit.id}:income`] = `Dochód mieści się w progu — ${benefit.name}`
    for (const c of benefit.extra_conditions ?? []) texts[`${BENEFIT_PREFIX}${benefit.id}:${c.id}`] = c.question || c.text
  }
  return texts
}

const pln = new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 0 })

export function answerLabel(key: string, questions: QuestionTexts): string {
  if (FORM_LABELS[key]) return FORM_LABELS[key]
  if (key.startsWith(INCOME_PREFIX)) {
    const limit = Number(key.slice(INCOME_PREFIX.length).replace(',', '.'))
    return Number.isFinite(limit) ? `Dochód na osobę do ${pln.format(limit)} zł` : 'Dochód na osobę w rodzinie'
  }
  if (key === 'income_per_person') return 'Dochód na osobę w rodzinie'
  if (key.startsWith(BENEFIT_PREFIX)) return questions[key] ?? 'Odpowiedź przy jednym ze świadczeń'
  return key.replace(/[_:]+/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
}

/** Numer konta pokazujemy tylko z końcówką — to dane wrażliwe. */
export function maskAccount(nr: string): string {
  const digits = nr.replace(/\s+/g, '')
  return `•••• ${digits.slice(-4)}`
}

/** Dane do wniosków w kolejności do czytania; ulica, numer domu i lokalu łączone w jeden wiersz. */
export function applicationFacts(answers: Record<string, boolean | string>): { key: string; label: string; value: string }[] {
  const str = (k: string) => (typeof answers[k] === 'string' ? (answers[k] as string).trim() : '')
  const out: { key: string; label: string; value: string }[] = []
  const street = str('street')
  if (street) {
    const no = [str('house_no'), str('flat_no')].filter(Boolean).join('/')
    out.push({ key: 'street', label: 'Ulica i numer', value: no ? `${street} ${no}` : street })
  }
  for (const k of ['house_no', 'flat_no', 'phone', 'employer_email', 'account_number', 'za_zyciem_certificate']) {
    if (street && (k === 'house_no' || k === 'flat_no')) continue
    if (str(k)) out.push({ key: k, label: FORM_LABELS[k], value: answerValue(k, str(k)) })
  }
  return out
}

export function answerValue(key: string, value: boolean | string): string {
  if (typeof value === 'boolean') return value ? 'Tak' : 'Nie'
  if (key === 'account_number') return maskAccount(value)
  return value
}
