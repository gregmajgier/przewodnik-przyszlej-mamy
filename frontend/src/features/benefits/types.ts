// Typy odpowiadające backend/app/models/benefit.py, services/matching.py i services/benefit_service.py.

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
  tags: string[]
}

export interface Question {
  condition_id: string
  text: string
}

export interface Match {
  status: MatchStatus
  reasons: string[]
  unmet: string[]
  questions: Question[]
  eligible_children: number
}

export interface BenefitMatch {
  benefit: Benefit
  match: Match
  deadline_date: string | null
}

export interface AnalysisStep {
  key: string
  label: string
  detail: string
  status: 'done' | 'warning'
}

export interface Totals {
  national: number
  local: number
  fits: number
  maybe: number
  no: number
}

export interface NearestDeadline {
  benefit_id: string
  name: string
  date: string
  days_left: number
}

export interface Analysis {
  steps: AnalysisStep[]
  totals: Totals
  estimated_annual_total: number
  nearest_deadline: NearestDeadline | null
}

export interface Summary {
  family_name: string
  totals: Totals
  estimated_annual_total: number
  nearest_deadline: NearestDeadline | null
  warnings: string[]
  parameters_label: string
}
