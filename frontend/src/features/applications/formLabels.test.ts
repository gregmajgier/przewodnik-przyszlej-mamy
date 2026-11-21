import { describe, expect, it } from 'vitest'
import { applyActions, recipientLabel } from './formLabels'
import { FORMS } from './testData'

describe('etykiety wniosków po ludzku', () => {
  it('adresat z katalogu zamiast wewnętrznego kodu', () => {
    expect(recipientLabel('URLOP-MAC-ROD', { institution: 'pracodawca' })).toBe('Wniosek dla pracodawcy')
    expect(recipientLabel('ZAM', { institution: 'ZUS lub płatnik' })).toBe('Wniosek do ZUS')
    expect(recipientLabel('SR-1', { institution: 'gmina (MOPS/OPS)' })).toBe('Wniosek do gminy')
    expect(recipientLabel('ODPIS-AKTU', { institution: 'USC' })).toBe('Wniosek do urzędu stanu cywilnego')
  })

  it('bez katalogu: wnioski do pracodawcy rozpoznajemy po kodzie, reszta dostaje ogólny podpis', () => {
    expect(recipientLabel('URLOP-OJC')).toBe('Wniosek dla pracodawcy')
    expect(recipientLabel('REZYGNACJA-MAC')).toBe('Wniosek dla pracodawcy')
    expect(recipientLabel('800PLUS')).toBe('Złóż wniosek')
  })

  it('jeden przycisk na adresata, w kolejności z danych świadczenia, żaden nie pokazuje kodu', () => {
    const actions = applyActions(['URLOP-MAC-ROD', 'ZAM'], FORMS.forms)
    expect(actions).toEqual([
      { code: 'URLOP-MAC-ROD', label: 'Wniosek dla pracodawcy' },
      { code: 'ZAM', label: 'Wniosek do ZUS' },
    ])
    expect(applyActions(['URLOP-ROD', 'URLOP-ROD-PRACA'])).toEqual([{ code: 'URLOP-ROD', label: 'Wniosek dla pracodawcy' }])
    expect(applyActions([])).toEqual([])
    expect(actions.every((a) => !/[A-Z]{3,}-/.test(a.label))).toBe(true)
  })
})
