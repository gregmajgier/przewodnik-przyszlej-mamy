// Typy odpowiadające backend/app/models/application.py, routers/applications.py i services/agent_plan.py.

export type Channel = 'employer_email' | 'portal_agent' | 'pdf_download'

export type AppStatus =
  | 'draft'
  | 'needs_input'
  | 'ready'
  | 'sent'
  | 'received'
  | 'more_info'
  | 'accepted'
  | 'rejected'
  | 'cancelled'

export type FieldType = 'text' | 'date' | 'bool' | 'choice'

export interface FieldInfo {
  id: string
  label: string
  type: FieldType
  required: boolean
  choices: string[] | null
}

export interface Question {
  field_id: string
  label: string
  type: FieldType
  choices: string[] | null
}

export type AnswerValue = string | boolean

export interface Application {
  id: string
  family_id: string
  applicant_id: string
  form_code: string
  child_id: string | null
  channel: Channel
  status: AppStatus
  values: Record<string, unknown>
  missing: Question[]
  recipient_email: string | null
  recipient_domain: string | null
  thread_id: string | null
  signed_at: string | null
  sent_at: string | null
  created_at: string
  fields: FieldInfo[]
}

export interface FormEntry {
  code: string
  name: string
  institution: string | null
  deadline: string | null
  channels: Channel[]
  default_channel: Channel
  only_electronic: boolean
  requires_child: boolean
  portal_id: string | null
}

export interface FormsResponse {
  forms: FormEntry[]
  recommended_flow: string[]
}

export type PortalKind = 'ezus' | 'empatia'

export interface AgentStep {
  field_id: string
  label: string
  value: unknown
  reason: string
}

export interface AgentPlan {
  application_id: string
  portal_id: string
  title: string | null
  kind: PortalKind
  steps: AgentStep[]
  blocked: Question[]
}

export const STATUS_LABEL: Record<AppStatus, string> = {
  draft: 'Szkic',
  needs_input: 'Brakuje danych',
  ready: 'Gotowy do wysłania',
  sent: 'Wysłany',
  received: 'Odebrany',
  more_info: 'Potrzeba dodatkowych informacji',
  accepted: 'Przyznany',
  rejected: 'Odrzucony',
  cancelled: 'Anulowany',
}

export const CHANNEL_LABEL: Record<Channel, string> = {
  employer_email: 'E-mail do pracodawcy (PDF w załączniku)',
  portal_agent: 'Agent wypełnia makietę portalu',
  pdf_download: 'PDF do pobrania i samodzielnego złożenia',
}

/** Statusy, po których wniosek jest zamknięty (nie ma już czego uzupełniać ani wysyłać). */
export const FINAL_STATUSES: AppStatus[] = ['sent', 'received', 'more_info', 'accepted', 'rejected', 'cancelled']

export function isFinal(status: AppStatus): boolean {
  return FINAL_STATUSES.includes(status)
}
