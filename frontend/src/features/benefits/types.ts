// Typy odpowiadające backend/app/models/benefit.py i services/benefit_service.py.

export type MatchStatus = 'fits' | 'maybe' | 'no'

export interface Benefit {
  id: string
  name: string
  scope: 'national' | 'regional' | 'municipal'
  unit_id: string | null
  category: 'benefit' | 'perk'
  description: string
  amount_text: string | null
  annual_value_estimate: number | null
  how_to_apply: string
  form_codes: string[]
  source_url: string
  extra_text: string | null
  verify: boolean
  /** świadczenie „na dziecko” — silnik wskazuje dzieci w `match.child_ids` */
  per_child?: boolean
}

export interface MatchQuestion {
  condition_id: string
  text: string
}

export interface MatchResult {
  status: MatchStatus
  reasons: string[]
  unmet: string[]
  questions: MatchQuestion[]
  /** dzieci, których dotyczy świadczenie `per_child` */
  child_ids?: string[]
}

/** Kto wypłaci zasiłek i gdzie złożyć dokumenty (backend/app/services/payout.py), jeden wpis na tytuł ubezpieczenia. */
export interface Payout {
  parent_name: string
  title: string
  payer: string
  paid_by: 'payer' | 'zus' | 'unknown' | 'none'
  headline: string
  why: string
  where: string
  /** wniosek, który ta osoba składa sama; null = nic nie składa (np. pracownik na zwolnieniu e-ZLA) */
  form_code?: string | null
}

export interface BenefitMatch {
  benefit: Benefit
  match: MatchResult
  payouts?: Payout[]
}

export interface Totals {
  national: number
  local: number
  fits: number
  maybe: number
  no: number
}

export interface Summary {
  totals: Totals
  estimated_annual_total: number
  nearest_deadline: { date: string; benefit_id: string; benefit_name: string } | null
  parameters_label: string
}

export interface AnalysisStep {
  key: string
  label: string
  detail: string
  status: string
}

export interface Analysis extends Summary {
  steps: AnalysisStep[]
}

export const STATUS_LABEL: Record<MatchStatus, string> = {
  fits: 'Pasuje',
  maybe: 'Może ci przysługiwać',
  no: 'Nie pasuje',
}
