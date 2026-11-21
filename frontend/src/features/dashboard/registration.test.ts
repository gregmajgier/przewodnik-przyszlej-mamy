import { describe, expect, it } from 'vitest'
import { featureRoutes, navItems, widgets } from '../registry'
import { dashboardWidgets } from './widgets'

describe('rejestracja funkcji: dashboard, analiza, świadczenia', () => {
  it('trasy są wykryte automatycznie (dashboard zastępuje przekierowanie „/”)', () => {
    const paths = featureRoutes.map((r) => r.path)
    expect(paths).toEqual(expect.arrayContaining(['/', '/analiza', '/swiadczenia']))
  })

  it('nawigacja: Start pierwszy, potem Świadczenia', () => {
    const labels = navItems.map((n) => n.label)
    expect(labels.indexOf('Start')).toBeLessThan(labels.indexOf('Świadczenia'))
    expect(navItems.find((n) => n.label === 'Start')?.path).toBe('/')
  })

  it('widget świadczeń trafia do rejestru i na dashboard', () => {
    expect(widgets.length).toBeGreaterThanOrEqual(1)
    expect(dashboardWidgets.length).toBe(widgets.length)
    const orders = dashboardWidgets.map((w) => w.order)
    expect(orders).toEqual([...orders].sort((a, b) => a - b))
  })
})
