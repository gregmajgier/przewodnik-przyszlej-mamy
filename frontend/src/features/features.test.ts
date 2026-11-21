import { describe, expect, it } from 'vitest'
import { featureRoutes, navItems } from './registry'

// Funkcje planów 03 i 08 dokładają się do aplikacji same (import.meta.glob) — sprawdzamy, że rejestr je widzi.
describe('rejestr funkcji: plany 03 i 08', () => {
  const paths = featureRoutes.map((r) => r.path)

  it('trasy świadczeń, analizy, panelu i wniosków są zarejestrowane, bez duplikatów', () => {
    for (const p of ['/', '/analiza', '/swiadczenia', '/wnioski', '/wnioski/nowy', '/wnioski/:id']) {
      expect(paths, `brak trasy ${p}`).toContain(p)
    }
    expect(new Set(paths).size).toBe(paths.length)
  })

  it('makiety portali są trasami publicznymi (bez powłoki aplikacji)', () => {
    const sim = featureRoutes.filter((r) => r.path?.startsWith('/sim/'))
    expect(sim.map((r) => r.path).sort()).toEqual(['/sim/empatia/:portalId', '/sim/ezus/:portalId'])
    expect(sim.every((r) => (r.handle as { public?: boolean } | undefined)?.public === true)).toBe(true)
  })

  it('pozostałe trasy nowych funkcji są chronione sesją (nie są publiczne)', () => {
    const own = featureRoutes.filter((r) => ['/', '/analiza', '/swiadczenia', '/wnioski', '/wnioski/nowy', '/wnioski/:id'].includes(r.path ?? ''))
    expect(own).toHaveLength(6)
    expect(own.every((r) => (r.handle as { public?: boolean } | undefined)?.public !== true)).toBe(true)
  })

  it('nawigacja rodzica: Panel, Świadczenia, Wnioski w kolejności', () => {
    const labels = navItems.filter((n) => n.area === 'parent').map((n) => n.label)
    expect(labels.indexOf('Panel')).toBeLessThan(labels.indexOf('Świadczenia'))
    expect(labels.indexOf('Świadczenia')).toBeLessThan(labels.indexOf('Wnioski'))
    expect(labels.indexOf('Wnioski')).toBeLessThan(labels.indexOf('Rodzina'))
  })

  it('logowanie, onboarding, analiza i czat są poza panelem (ekrany przepływu), sprawy domowników w panelu', () => {
    const handle = (path: string) => featureRoutes.find((r) => r.path === path)?.handle as { flow?: boolean; public?: boolean } | undefined
    for (const p of ['/start', '/dolacz', '/analiza', '/czat']) expect(handle(p)?.flow, p).toBe(true)
    expect(handle('/logowanie')?.public).toBe(true)
    expect(paths).toContain('/sprawy/:who')
    expect(handle('/sprawy/:who')?.flow).toBeUndefined()
  })
})
