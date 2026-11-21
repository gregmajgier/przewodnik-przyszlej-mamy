import type { Child, FamilyView } from '../lib/types'
import { ANNA } from './utils'

function child(over: Partial<Child> & Pick<Child, 'id' | 'name'>): Child {
  return {
    family_id: 'f1',
    birth_date: null,
    due_date: null,
    status: 'born',
    pesel: null,
    has_disability: false,
    foster: false,
    situation: null,
    situation_kind: null,
    situation_at: null,
    serious_illness: false,
    ...over,
  }
}

/** Data względem dziś: `yearsAgo` lat i `extraDays` dni temu (ISO). */
export function isoDaysAgo(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString().slice(0, 10)
}

export const MAJA = child({ id: 'c-maja', name: 'Maja', birth_date: isoDaysAgo(7 * 365 + 90) })
export const ANTEK = child({ id: 'c-antek', name: 'Antek', birth_date: isoDaysAgo(3 * 365 + 120) })
export const UNBORN = child({ id: 'c-unborn', name: 'Dziecko w drodze', status: 'expected', due_date: isoDaysAgo(-60) })

export function familyOf(children: Child[] = [MAJA, ANTEK, UNBORN], over: Partial<FamilyView> = {}): FamilyView {
  return {
    family: { id: 'f1', name: 'Rodzina Nowak', owner_id: ANNA.id, member_ids: [ANNA.id], invite_code: 'K7P2QX9M', invite_expires_at: null },
    members: [ANNA],
    children,
    pending_requests: [],
    ...over,
  }
}

export const NOWAK = familyOf()
