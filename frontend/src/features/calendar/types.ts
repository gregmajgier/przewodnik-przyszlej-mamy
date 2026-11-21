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
  muted?: boolean
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
