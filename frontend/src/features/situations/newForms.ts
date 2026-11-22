import { api } from '../../lib/api'
import { fetchSituation } from '../jaskolka/jaskolkaApi'
import type { SituationDetail } from '../jaskolka/jaskolkaApi'

const API_URL: string = import.meta.env.VITE_API_URL ?? ''

/**
 * Trudne sytuacje, dla których pokazujemy „nowe wnioski”. Identyfikatory są te same co w `jaskolka.json`
 * (`/api/jaskolka/situations/{id}`): trzy rodzaje straty z `SituationMenu` i „Za życiem” → `ciezka-choroba`.
 */
export type HardSituation = 'poronienie' | 'martwe-urodzenie' | 'smierc-dziecka' | 'ciezka-choroba'

/** Wpis katalogu `GET /api/wnioski` (backend/app/data/katalog_wnioskow_pdf.json); tylko pola, których używamy. */
export interface CatalogForm {
  kod: string
  nazwa: string
  instytucja?: string | null
  plik_lokalny?: string | null
}

export interface BenefitRow {
  benefit: { form_codes: string[] }
  match: { status: 'fits' | 'maybe' | 'no' }
}

export type NewFormAction = { kind: 'wizard'; href: string } | { kind: 'pdf'; href: string } | { kind: 'info' }

export interface NewForm {
  code: string
  name: string
  institution: string | null
  action: NewFormAction
}

/** Kody wniosków z checklisty sytuacji, bez powtórzeń, w kolejności z checklisty. */
export function situationFormCodes(detail: SituationDetail): string[] {
  return [...new Set(detail.checklist.flatMap((item) => item.form_codes))]
}

/**
 * Kody, które chowa deterministyczne dopasowanie świadczeń: każde świadczenie z tym kodem ma status `no`
 * (np. ZAM, gdy rodzic nie podlega ubezpieczeniu chorobowemu). Kod bez świadczenia w katalogu zostaje.
 */
export function hiddenByMatching(rows: BenefitRow[]): Set<string> {
  const statuses = new Map<string, string[]>()
  for (const row of rows) {
    for (const code of row.benefit.form_codes) statuses.set(code, [...(statuses.get(code) ?? []), row.match.status])
  }
  return new Set([...statuses].filter(([, list]) => list.every((s) => s === 'no')).map(([code]) => code))
}

export function buildNewForms(
  codes: string[],
  catalog: CatalogForm[],
  wizardCodes: Set<string>,
  hidden: Set<string>,
  childId: string,
): NewForm[] {
  const byCode = new Map(catalog.map((f) => [f.kod, f]))
  return codes
    .filter((code) => !hidden.has(code))
    .map((code) => {
      const entry = byCode.get(code)
      const action: NewFormAction = wizardCodes.has(code)
        ? { kind: 'wizard', href: `/wnioski/nowy?form=${encodeURIComponent(code)}&child=${encodeURIComponent(childId)}` }
        : entry?.plik_lokalny
          ? { kind: 'pdf', href: `${API_URL}/api/wnioski/${encodeURIComponent(code)}/pdf` }
          : { kind: 'info' }
      return { code, name: entry?.nazwa ?? code, institution: entry?.instytucja ?? null, action }
    })
}

/** „1 wniosek”, „2 wnioski”, „5 wniosków”, „12 wniosków”, „22 wnioski”. */
export function plWnioski(n: number): string {
  if (n === 1) return '1 wniosek'
  const lastTwo = n % 100
  const last = n % 10
  return last >= 2 && last <= 4 && !(lastTwo >= 12 && lastTwo <= 14) ? `${n} wnioski` : `${n} wniosków`
}

/**
 * Wnioski, które rodzic może złożyć po zgłoszeniu sytuacji. Lista pochodzi z checklisty sytuacji (ta sama treść co
 * `/jaskolka`), nazwy z katalogu wniosków; kreator w aplikacji ma pierwszeństwo przed pustym PDF. Brak katalogu,
 * listy kreatorów albo dopasowań nie blokuje wyniku (pokazujemy wtedy mniej szczegółów).
 */
export async function loadNewForms(situation: HardSituation, childId: string): Promise<NewForm[]> {
  const detail = await fetchSituation(situation)
  const [catalog, forms, benefits] = await Promise.all([
    api<CatalogForm[]>('/api/wnioski').catch(() => [] as CatalogForm[]),
    api<{ forms: { code: string }[] }>('/api/applications/forms').catch(() => ({ forms: [] as { code: string }[] })),
    api<BenefitRow[]>('/api/benefits').catch(() => [] as BenefitRow[]),
  ])
  const wizard = new Set(forms.forms.map((f) => f.code))
  return buildNewForms(situationFormCodes(detail), catalog, wizard, hiddenByMatching(benefits), childId)
}
