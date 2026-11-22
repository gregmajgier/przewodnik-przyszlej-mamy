import { describe, expect, it } from 'vitest'
import { eventAction, isAtRisk } from './types'
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

describe('eventAction', () => {
  const deadline = { ...base, kind: 'deadline', severity: null, source_ref: 'benefit:zas', form_code: 'ZAM', child_id: 'c1' } as CalendarEvent

  it('termin ze świadczenia prowadzi do kreatora z wnioskiem i dzieckiem', () => {
    expect(eventAction(deadline)).toEqual({ to: '/wnioski/nowy?form=ZAM&child=c1', label: 'Złóż wniosek' })
    expect(eventAction({ ...deadline, child_id: null })?.to).toBe('/wnioski/nowy?form=ZAM')
  })

  it('wpis o wniosku prowadzi do tego wniosku', () => {
    const app = { ...base, kind: 'application', severity: null, source_ref: 'application:a1', status: 'draft' } as CalendarEvent
    expect(eventAction(app)).toEqual({ to: '/wnioski/a1', label: 'Otwórz wniosek' })
    expect(eventAction({ ...app, status: 'sent' })?.label).toBe('Zobacz wniosek')
  })

  it('bez przycisku: termin bez kreatora, zrobiony, wyciszony i ostrzeżenie', () => {
    expect(eventAction({ ...deadline, form_code: null })).toBeNull()
    expect(eventAction({ ...deadline, done: true })).toBeNull()
    expect(eventAction({ ...deadline, muted: true })).toBeNull()
    expect(eventAction(base)).toBeNull()
  })
})
