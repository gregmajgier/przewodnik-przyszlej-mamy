import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderWithSession } from '../../test/utils'
import { BenefitSheet } from './BenefitSheet'
import type { BenefitMatch, Payout } from './types'

const PAYOUT: Payout = {
  parent_name: 'Anna',
  title: 'umowa o pracę',
  payer: 'Krakowskie Centrum Usług Wspólnych Sp. z o.o.',
  paid_by: 'payer',
  headline: 'Zasiłek wypłaci pracodawca',
  why: 'Krakowskie Centrum Usług Wspólnych Sp. z o.o. zgłasza do ubezpieczenia chorobowego więcej niż 20 osób.',
  where: 'Wniosek o urlop składasz w kadrach.',
}

function item(status: 'fits' | 'no', payouts?: Payout[], formCodes: string[] = []): BenefitMatch {
  return {
    benefit: {
      id: 'nat-zasilek-macierzynski',
      name: 'Urlop i zasiłek macierzyński',
      scope: 'national',
      unit_id: null,
      category: 'benefit',
      description: 'opis',
      amount_text: null,
      annual_value_estimate: null,
      how_to_apply: 'jak',
      form_codes: formCodes,
      source_url: 'https://www.zus.pl',
      extra_text: null,
      verify: false,
    },
    match: { status, reasons: [], unmet: status === 'no' ? ['powód'] : [], questions: [] },
    payouts,
  }
}

const noop = () => {}

describe('BenefitSheet — kto wypłaci zasiłek', () => {
  it('pokazuje, kto wypłaci zasiłek i gdzie złożyć dokumenty', () => {
    renderWithSession(<BenefitSheet item={item('fits', [PAYOUT])} onClose={noop} onAnswer={noop} />)
    expect(screen.getByRole('heading', { name: 'Kto wypłaci zasiłek i gdzie złożyć dokumenty' })).toBeInTheDocument()
    expect(screen.getByText('Zasiłek wypłaci pracodawca')).toBeInTheDocument()
    expect(screen.getByText(/Anna · umowa o pracę · Krakowskie Centrum/)).toBeInTheDocument()
    expect(screen.getByText('Wniosek o urlop składasz w kadrach.')).toBeInTheDocument()
  })

  it('nie pokazuje sekcji, gdy świadczenie nie pasuje', () => {
    renderWithSession(<BenefitSheet item={item('no', [PAYOUT])} onClose={noop} onAnswer={noop} />)
    expect(screen.queryByText('Kto wypłaci zasiłek i gdzie złożyć dokumenty')).not.toBeInTheDocument()
  })

  it('nie proponuje wniosku, gdy osoba nic nie składa (pracownik na e-ZLA)', () => {
    const employee = { ...PAYOUT, form_code: null }
    renderWithSession(<BenefitSheet item={item('fits', [employee], ['ZAS-53'])} onClose={noop} onAnswer={noop} />)
    expect(screen.queryByRole('link', { name: /Złóż wniosek/ })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Źródło/ })).toBeInTheDocument()
  })

  it('prowadzi do wniosku właściwego dla tytułu ubezpieczenia', () => {
    const owner = { ...PAYOUT, form_code: 'ZAS-53' }
    renderWithSession(<BenefitSheet item={item('fits', [owner], ['ZAS-53'])} onClose={noop} onAnswer={noop} />)
    expect(screen.getByRole('link', { name: /Złóż wniosek/ })).toHaveAttribute('href', '/wnioski/nowy?form=ZAS-53')
  })

  it('bez danych o wypłacie zostaje pierwszy wniosek z katalogu', () => {
    renderWithSession(<BenefitSheet item={item('fits', [], ['URLOP-OJC', 'ZAM'])} onClose={noop} onAnswer={noop} />)
    expect(screen.getByRole('link', { name: /Złóż wniosek/ })).toHaveAttribute('href', '/wnioski/nowy?form=URLOP-OJC')
  })

  it('działa ze starszą odpowiedzią API bez pola payouts', () => {
    renderWithSession(<BenefitSheet item={item('fits')} onClose={noop} onAnswer={noop} />)
    expect(screen.queryByText('Kto wypłaci zasiłek i gdzie złożyć dokumenty')).not.toBeInTheDocument()
    expect(screen.getByText('Jak to załatwić')).toBeInTheDocument()
  })
})
