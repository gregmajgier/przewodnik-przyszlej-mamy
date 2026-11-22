import { describe, expect, it } from 'vitest'
import type { Child } from '../../lib/types'
import { guidesFor, type Person } from './model'

function kidPerson(child: Child, months: number): Person {
  return { key: child.id, kind: 'child', name: child.name, subtitle: '', tone: 'mint', child, months }
}

const MAJA: Child = {
  id: 'c-maja', family_id: 'f1', name: 'Maja', birth_date: '2019-08-25', due_date: null, status: 'born', pesel: null,
  has_disability: false, foster: false, situation: null, situation_kind: null, situation_at: null, serious_illness: false,
}

describe('guidesFor: Dobry Start', () => {
  const maja = kidPerson(MAJA, 87)
  const find = (today: Date) => guidesFor(maja, [maja], today).find((g) => g.id === 'kid-dobry-start')

  it('w oknie naboru prowadzi do kreatora wniosku z dzieckiem', () => {
    expect(find(new Date(2026, 10, 22))?.action).toEqual({ label: 'Złóż wniosek', to: '/wnioski/nowy?form=DOBRY-START&child=c-maja' })
  })

  it('poza oknem naboru (1.07–30.11) nie ma przycisku', () => {
    expect(find(new Date(2026, 0, 15))?.action).toBeUndefined()
  })
})
