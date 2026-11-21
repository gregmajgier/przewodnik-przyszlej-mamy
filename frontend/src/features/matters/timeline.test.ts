import { describe, expect, it } from 'vitest'
import type { Child } from '../../lib/types'
import { childTimeline, relativeIn, stageOf } from './timeline'

const TODAY = new Date(2026, 10, 21) // 21.11.2026

function kid(over: Partial<Child>): Child {
  return {
    id: 'c1', family_id: 'f1', name: 'Maja', birth_date: null, due_date: null, status: 'born', pesel: null,
    has_disability: false, foster: false, situation: null, situation_kind: null, situation_at: null, serious_illness: false,
    ...over,
  }
}

const titles = (xs: { title: string }[]) => xs.map((x) => x.title)

describe('stageOf', () => {
  it('uczeń: wiek i klasa liczona od roku urodzenia (rocznik 2019 → 1. klasa w roku 2026/27)', () => {
    expect(stageOf(kid({ birth_date: '2019-08-25' }), TODAY)).toEqual({ title: '7 lat', stage: '1. klasa' })
    expect(stageOf(kid({ birth_date: '2017-01-10' }), TODAY)).toEqual({ title: '9 lat', stage: '3. klasa' })
  })
  it('przedszkolak i zerówka', () => {
    expect(stageOf(kid({ birth_date: '2023-07-25' }), TODAY)).toEqual({ title: '3 lata', stage: 'przedszkole' })
    expect(stageOf(kid({ birth_date: '2020-03-10' }), TODAY)).toEqual({ title: '6 lat', stage: 'zerówka' })
  })
  it('szkoła średnia', () => {
    expect(stageOf(kid({ birth_date: '2010-05-01' }), TODAY).stage).toBe('2. klasa szkoły średniej')
  })
  it('niemowlę: miesiące, bez etapu', () => {
    expect(stageOf(kid({ birth_date: '2026-05-21' }), TODAY)).toEqual({ title: '6 miesięcy', stage: null })
  })
  it('dziecko w drodze', () => {
    expect(stageOf(kid({ status: 'expected', due_date: '2027-01-20' }), TODAY)).toEqual({ title: 'W drodze', stage: 'termin 20.01.2027' })
  })
})

describe('relativeIn', () => {
  it('dni, tygodnie, miesiące, lata', () => {
    expect(relativeIn(new Date(2026, 10, 22), TODAY)).toBe('jutro')
    expect(relativeIn(new Date(2026, 10, 25), TODAY)).toBe('za 4 dni')
    expect(relativeIn(new Date(2026, 11, 8), TODAY)).toBe('za 2 tygodnie')
    expect(relativeIn(new Date(2027, 6, 1), TODAY)).toBe('za 7 miesięcy')
    expect(relativeIn(new Date(2029, 8, 1), TODAY)).toBe('za 2 lata')
    expect(relativeIn(new Date(2031, 8, 1), TODAY)).toBe('za 4 lata')
  })
})

describe('childTimeline', () => {
  it('7-latka: zapisy i 1. klasa za nami; przed nami Dobry Start i kolejne etapy', () => {
    const t = childTimeline(kid({ birth_date: '2019-08-25' }), TODAY)
    expect(titles(t.past)).toEqual(['Zapisy do 1. klasy', '1. klasa'])
    expect(t.next[0].title).toBe('Dobry Start — nabór wniosków')
    expect(t.next[0].date).toEqual(new Date(2027, 6, 1))
    expect(titles(t.next)).toContain('Egzamin ósmoklasisty')
    expect(t.next).toHaveLength(4)
    expect(t.all.length).toBeGreaterThan(t.past.length + t.next.length)
    // chronologicznie
    const dates = t.all.map((m) => m.date.getTime())
    expect([...dates].sort((a, b) => a - b)).toEqual(dates)
  })

  it('3-latek: przed nami zerówka i szkoła; Dobrego Startu jeszcze nie ma', () => {
    const t = childTimeline(kid({ birth_date: '2023-07-25' }), TODAY)
    expect(titles(t.past)).toEqual(['Rekrutacja do przedszkola', 'Przedszkole'])
    expect(titles(t.next).slice(0, 2)).toEqual(['Zapisy do zerówki', 'Zerówka'])
    expect(titles(t.next)).not.toContain('Dobry Start — nabór wniosków')
  })

  it('dziecko w drodze: najpierw narodziny, potem formalności liczone od terminu', () => {
    const t = childTimeline(kid({ status: 'expected', due_date: '2027-01-20' }), TODAY)
    expect(t.past).toEqual([])
    expect(titles(t.next)).toEqual(['Narodziny', 'Zgłoszenie urodzenia', 'Wniosek o 800+', 'Roczek'])
    expect(t.next[0].date).toEqual(new Date(2027, 0, 20))
  })

  it('nastolatek: 18. urodziny i matura przed nami', () => {
    const t = childTimeline(kid({ birth_date: '2010-05-01' }), TODAY)
    expect(titles(t.next)).toEqual(expect.arrayContaining(['18. urodziny', 'Matura']))
  })
})
