// Odpowiada backend/app/models/calendar.py (plan 09).
export interface CalendarEvent {
  id: string
  family_id: string
  kind: 'deadline' | 'application' | 'child' | 'warning'
  title: string
  summary: string
  due_date: string | null
  effect_until: string | null
  done: boolean
  overdue: boolean
  source_ref: string
  child_id: string | null
  actor_user_id: string | null
  actor_name: string | null
  recipient: string | null
  status: string | null
  severity: 'info' | 'medium' | 'high' | null
  /** termin ze świadczenia: kod wniosku do złożenia */
  form_code?: string | null
  muted?: boolean
}

export interface EventAction {
  to: string
  label: string
}

/**
 * Dokąd z karty kalendarza prowadzi przycisk: do istniejącego wniosku albo do kreatora nowego
 * (z dzieckiem, jeśli termin dotyczy konkretnego dziecka). Wstrzymane wpisy (tryb jaskółki) nie wołają do działania.
 */
export function eventAction(e: CalendarEvent): EventAction | null {
  if (e.muted) return null
  if (e.kind === 'application' && e.source_ref.startsWith('application:')) {
    const id = e.source_ref.slice('application:'.length)
    return { to: `/wnioski/${encodeURIComponent(id)}`, label: e.done || e.status === 'sent' ? 'Zobacz wniosek' : 'Otwórz wniosek' }
  }
  if (e.kind === 'deadline' && e.form_code && !e.done) {
    const child = e.child_id ? `&child=${encodeURIComponent(e.child_id)}` : ''
    return { to: `/wnioski/nowy?form=${encodeURIComponent(e.form_code)}${child}`, label: 'Złóż wniosek' }
  }
  return null
}

export const KIND_LABEL: Record<CalendarEvent['kind'], string> = {
  deadline: 'Termin',
  application: 'Wniosek',
  child: 'Dziecko',
  warning: 'Ostrzeżenie',
}

export function isAtRisk(e: CalendarEvent): boolean {
  return !e.done && !e.muted && (e.overdue || e.kind === 'warning')
}
