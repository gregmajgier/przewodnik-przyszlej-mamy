import { describe, expect, it } from 'vitest'
import type { SituationDetail } from '../jaskolka/jaskolkaApi'
import { buildNewForms, hiddenByMatching, plWnioski, situationFormCodes } from './newForms'
import type { BenefitRow, CatalogForm } from './newForms'

function detail(codes: string[][]): SituationDetail {
  return {
    id: 'poronienie',
    label: 'Poronienie',
    intro: '',
    checklist: codes.map((form_codes, i) => ({
      id: `i${i}`,
      title: 't',
      body: 'b',
      kind: 'right',
      deadline_text: null,
      form_codes,
      source_url: 'https://www.gov.pl/x',
      verify: false,
    })),
  }
}

const CATALOG: CatalogForm[] = [
  { kod: 'ZAM', nazwa: 'Wniosek o zasiłek macierzyński', instytucja: 'ZUS lub płatnik', plik_lokalny: null },
  { kod: 'Z-12', nazwa: 'Wniosek o zasiłek pogrzebowy', instytucja: 'ZUS', plik_lokalny: 'wnioski_pdf/Z-12_pdf_do_druku.pdf' },
  { kod: 'ODPIS-AKTU', nazwa: 'Wniosek o odpis aktu urodzenia', instytucja: 'USC', plik_lokalny: null },
]

const row = (codes: string[], status: BenefitRow['match']['status']): BenefitRow => ({ benefit: { form_codes: codes }, match: { status } })

describe('newForms', () => {
  it('kody z checklisty bez powtórzeń, w kolejności', () => {
    expect(situationFormCodes(detail([[], ['ZAM'], ['ODPIS-AKTU'], ['Z-12'], ['ZAM']]))).toEqual(['ZAM', 'ODPIS-AKTU', 'Z-12'])
  })

  it('dopasowanie chowa kod tylko wtedy, gdy każde świadczenie z nim ma status „no”', () => {
    expect(hiddenByMatching([row(['ZAM'], 'no')])).toEqual(new Set(['ZAM']))
    expect(hiddenByMatching([row(['ZAM'], 'no'), row(['ZAM'], 'maybe')])).toEqual(new Set())
    expect(hiddenByMatching([row(['ZA-ZYCIEM'], 'fits')])).toEqual(new Set())
    expect(hiddenByMatching([])).toEqual(new Set())
  })

  it('kreator ma pierwszeństwo, potem pusty PDF, na końcu sama informacja', () => {
    const forms = buildNewForms(['ZAM', 'ODPIS-AKTU', 'Z-12'], CATALOG, new Set(['ZAM']), new Set(), 'c1')
    expect(forms.map((f) => [f.code, f.action.kind])).toEqual([
      ['ZAM', 'wizard'],
      ['ODPIS-AKTU', 'info'],
      ['Z-12', 'pdf'],
    ])
    expect(forms[0].action).toEqual({ kind: 'wizard', href: '/wnioski/nowy?form=ZAM&child=c1' })
    expect(forms[2].action.kind === 'pdf' && forms[2].action.href.endsWith('/api/wnioski/Z-12/pdf')).toBe(true)
    expect(forms[1]).toMatchObject({ name: 'Wniosek o odpis aktu urodzenia', institution: 'USC' })
  })

  it('pomija ukryte kody; bez katalogu pokazuje sam kod', () => {
    const forms = buildNewForms(['ZAM', 'Z-12'], [], new Set(), new Set(['ZAM']), 'c1')
    expect(forms).toEqual([{ code: 'Z-12', name: 'Z-12', institution: null, action: { kind: 'info' } }])
  })

  it('odmiana „wniosek”', () => {
    expect([1, 2, 3, 4, 5, 11, 12, 14, 22, 25].map(plWnioski)).toEqual([
      '1 wniosek',
      '2 wnioski',
      '3 wnioski',
      '4 wnioski',
      '5 wniosków',
      '11 wniosków',
      '12 wniosków',
      '14 wniosków',
      '22 wnioski',
      '25 wniosków',
    ])
  })
})
