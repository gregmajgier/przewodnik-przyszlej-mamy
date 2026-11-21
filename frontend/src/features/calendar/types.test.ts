import { describe, expect, it } from 'vitest'
import { isAtRisk } from './types'
import type { CalendarEvent } from './types'

const base = {
  id: 'e', family_id: 'f', kind: 'warning', title: 't', summary: 's', due_date: null, effect_until: null,
  done: false, overdue: false, source_ref: 'x', child_id: null, actor_user_id: null, actor_name: null,
  recipient: null, status: null, severity: 'high',
} as CalendarEvent

describe('isAtRisk', () => {
  it('ostrzeżenie jest zagrożone, chyba że wyciszone (tryb jaskółki) albo zrobione', () => {
    expect(isAtRisk(base)).toBe(true)
    expect(isAtRisk({ ...base, muted: true })).toBe(false)
    expect(isAtRisk({ ...base, done: true })).toBe(false)
  })
})
