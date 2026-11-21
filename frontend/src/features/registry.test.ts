import { describe, expect, it } from 'vitest'
import { buildRegistry, featureRoutes, navItems, sortByOrder } from './registry'

describe('registry', () => {
  it('sortuje elementy po order (stabilnie, bez mutacji wejścia)', () => {
    const input = [
      { order: 30, id: 'c' },
      { order: 10, id: 'a' },
      { order: 20, id: 'b' },
    ]
    expect(sortByOrder(input).map((i) => i.id)).toEqual(['a', 'b', 'c'])
    expect(input[0].id).toBe('c')
  })

  it('buildRegistry składa trasy, nawigację i widgety z modułów', () => {
    const Comp = () => null
    const reg = buildRegistry({
      routes: {
        './a/routes.tsx': { default: [{ path: '/a' }] },
        './b/routes.tsx': { default: [{ path: '/b' }, { path: '/b2' }] },
      },
      nav: {
        './b/nav.ts': { default: { label: 'B', path: '/b', order: 20, area: 'parent' } },
        './a/nav.ts': { default: { label: 'A', path: '/a', order: 10, area: 'parent' } },
      },
      widgets: {
        './b/widget.tsx': { default: { order: 2, Component: Comp } },
        './a/widget.tsx': { default: { order: 1, Component: Comp } },
      },
      profileSections: {},
    })
    expect(reg.featureRoutes.map((r) => r.path)).toEqual(['/a', '/b', '/b2'])
    expect(reg.navItems.map((n) => n.label)).toEqual(['A', 'B'])
    expect(reg.widgets.map((w) => w.order)).toEqual([1, 2])
  })

  it('auto-wykrywa funkcje z features/*', () => {
    const paths = featureRoutes.map((r) => r.path)
    expect(paths).toContain('/logowanie')
    expect(paths).toContain('/rodzina')
    expect(paths).toContain('/dane')
    const labels = navItems.map((n) => n.label)
    expect(labels).toContain('Rodzina')
    expect(labels).toContain('Moje dane')
    const orders = navItems.map((n) => n.order)
    expect(orders).toEqual([...orders].sort((a, b) => a - b))
  })

  it('trasa logowania jest publiczna (poza powłoką)', () => {
    const login = featureRoutes.find((r) => r.path === '/logowanie')
    expect((login?.handle as { public?: boolean } | undefined)?.public).toBe(true)
  })
})
