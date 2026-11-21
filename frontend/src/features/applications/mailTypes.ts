// Odpowiada backend/app/routers/mail.py (plan 09).
export interface MailStatus {
  connected: boolean
  provider: string
  simulated: boolean
  address: string
  scope_note: string
}

export interface ThreadMessage {
  id: string
  folder: 'inbox' | 'sent'
  from_addr: string
  to_addr: string
  subject: string
  body: string
  received_at: string
  classification_status: string | null
  classification_confidence: number | null
  classification_summary: string | null
  needs_review: boolean
}

export interface MailThread {
  application: {
    id: string
    form_code: string
    status: string
    applicant_id: string
    applicant_name: string
    recipient_email: string | null
    sent_at: string
  }
  needs_review: boolean
  messages: ThreadMessage[]
}

export const APP_STATUS_LABEL: Record<string, string> = {
  sent: 'Wysłany',
  received: 'Otrzymany',
  more_info: 'Wezwanie do uzupełnienia',
  accepted: 'Zaakceptowany',
  rejected: 'Odrzucony',
}
