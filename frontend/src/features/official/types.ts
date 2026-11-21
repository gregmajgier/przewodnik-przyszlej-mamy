import type { PillTone } from '../../ui/controls'

// Typy panelu urzędnika (plan 07). Criteria/Condition/Benefit odpowiadają backend/app/models/benefit.py
// (+ `OfficialBenefit` w models/official_benefit.py: stan zatwierdzenia warunków).

export interface Criteria {
  child_age_min_months: number | null
  child_age_max_months: number | null
  max_income_per_person: number | null
  min_children: number | null
  requires_pregnancy: boolean | null
  pregnant_or_child_max_months: number | null
  requires_disability: boolean | null
  requires_foster: boolean | null
  employment_kinds: ('employment' | 'mandate' | 'jdg')[] | null
}

export interface Condition {
  id: string
  text: string
  kind: 'auto' | 'ask'
  question: string | null
  profile_key: string | null
}

export type BenefitStatus = 'draft' | 'awaiting_approval' | 'published'

export interface OfficialBenefit {
  id: string
  name: string
  scope: 'national' | 'regional' | 'municipal'
  unit_id: string | null
  category: 'benefit' | 'perk'
  description: string
  amount_text: string | null
  annual_value_estimate: number | null
  deadline_text: string | null
  how_to_apply: string
  apply_url: string | null
  source_url: string
  criteria: Criteria
  extra_conditions: Condition[]
  extra_text: string | null
  status: BenefitStatus
  conditions_approved: boolean
  updated_at: string | null
}

export type BenefitForm = Pick<
  OfficialBenefit,
  | 'name'
  | 'description'
  | 'category'
  | 'amount_text'
  | 'annual_value_estimate'
  | 'deadline_text'
  | 'how_to_apply'
  | 'apply_url'
  | 'source_url'
  | 'criteria'
  | 'extra_text'
>

export interface BenefitDraft {
  name: string
  description: string
  amount_text: string | null
  criteria: Criteria
  extra_text: string | null
}

export interface Unit {
  id: string
  name: string
  level: 'gmina' | 'powiat' | 'voivodeship'
}

export const EMPTY_CRITERIA: Criteria = {
  child_age_min_months: null,
  child_age_max_months: null,
  max_income_per_person: null,
  min_children: null,
  requires_pregnancy: null,
  pregnant_or_child_max_months: null,
  requires_disability: null,
  requires_foster: null,
  employment_kinds: null,
}

export const EMPTY_FORM: BenefitForm = {
  name: '',
  description: '',
  category: 'benefit',
  amount_text: null,
  annual_value_estimate: null,
  deadline_text: null,
  how_to_apply: '',
  apply_url: null,
  source_url: '',
  criteria: EMPTY_CRITERIA,
  extra_text: null,
}

export const STATUS_LABEL: Record<BenefitStatus, string> = {
  draft: 'Szkic',
  awaiting_approval: 'Warunki do zatwierdzenia',
  published: 'Opublikowane',
}

export function toForm(b: OfficialBenefit): BenefitForm {
  return {
    name: b.name,
    description: b.description,
    category: b.category,
    amount_text: b.amount_text,
    annual_value_estimate: b.annual_value_estimate,
    deadline_text: b.deadline_text,
    how_to_apply: b.how_to_apply,
    apply_url: b.apply_url,
    source_url: b.source_url,
    criteria: { ...EMPTY_CRITERIA, ...b.criteria },
    extra_text: b.extra_text,
  }
}

export const LEVEL_LABEL: Record<Unit['level'], string> = {
  gmina: 'Gmina',
  powiat: 'Powiat',
  voivodeship: 'Województwo',
}

/** Kolejny krok urzędnika przy świadczeniu w danym stanie. */
export const NEXT_STEP: Record<BenefitStatus, string> = {
  draft: 'Uzupełnij i opublikuj',
  awaiting_approval: 'Sprawdź i zatwierdź warunki',
  published: 'Widoczne dla rodziców',
}

/** Etykieta stanu — „do zatwierdzenia” po zatwierdzeniu warunków znaczy już „gotowe do publikacji”. */
export function statusLabel(b: Pick<OfficialBenefit, 'status' | 'conditions_approved'>): string {
  return b.status === 'awaiting_approval' && b.conditions_approved ? 'Gotowe do publikacji' : STATUS_LABEL[b.status]
}

export const STATUS_TONE: Record<BenefitStatus, PillTone> = {
  draft: 'neutral',
  awaiting_approval: 'amber',
  published: 'green',
}
