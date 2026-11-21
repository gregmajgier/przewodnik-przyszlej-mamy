// Typy odpowiadające modelom pydantic w backend/app/models.

export type Role = 'parent' | 'official'

export interface User {
  id: string
  role: Role
  name: string
  email: string | null
  persona_id: string | null
  family_id: string | null
  unit_id: string | null
}

export interface Persona {
  id: string
  name: string
  role_label: string
}

export interface Family {
  id: string
  name: string
  owner_id: string
  member_ids: string[]
  invite_code: string | null
  invite_expires_at: string | null
}

export interface Child {
  id: string
  family_id: string
  name: string
  birth_date: string | null
  due_date: string | null
  status: 'expected' | 'born'
  pesel: string | null
  has_disability: boolean
  foster: boolean
  situation: 'loss' | null
  situation_kind: 'poronienie' | 'martwe-urodzenie' | 'smierc-dziecka' | null
  situation_at: string | null
  /** rodzic wyszedł z trybu jaskółki (plan 10); dziecko zachowuje `situation` */
  situation_exited_at?: string | null
  serious_illness: boolean
}

export interface JoinRequest {
  id: string
  family_id: string
  user_id: string
  status: 'pending' | 'accepted' | 'rejected'
  user_name?: string
}

export interface FamilyView {
  family: Family
  members: User[]
  children: Child[]
  pending_requests: (JoinRequest & { user_name: string })[]
}

export interface Address {
  city: string
  gmina: string
  powiat: string
  voivodeship: string
  postal_code: string
}

export interface Insurance {
  kind: 'employment' | 'mandate' | 'jdg'
  payer: string
  contribution_base: number
  voluntary_sickness: boolean | null
  since: string
}

export interface Ezla {
  code: string
  from_date: string
  to_date: string
}

export interface KnownChild {
  name: string
  birth_date: string | null
  due_date: string | null
}

export interface ParentProfile {
  user_id: string
  first_name: string
  last_name: string
  pesel: string
  birth_date: string
  address: Address
  insurance: Insurance[]
  ezla: Ezla[]
  contribution_debt: { amount: number; since: string } | null
  known_children: KnownChild[]
  answers: Record<string, boolean | string>
}

export interface MemberProfile extends ParentProfile {
  user_name: string
}
