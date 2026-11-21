import type { ComponentType } from 'react'
import type { RouteObject } from 'react-router-dom'

export interface NavItem {
  label: string
  path: string
  order: number
  area: 'parent' | 'official'
}

export interface Widget {
  order: number
  Component: ComponentType
}

/** Sekcja profilu „Moje dane” dokładana przez inną funkcję (np. skan umów — plan 04). */
export interface ProfileSection {
  order: number
  title: string
  Component: ComponentType<{ userId: string; userName: string }>
}

/** Element w nagłówku powłoki (np. dzwonek powiadomień — plan 09): plik header-slot.tsx funkcji. */
export interface HeaderSlot {
  order: number
  Component: ComponentType
}

type Mods<T> = Record<string, { default: T }>

export interface RegistryInput {
  routes: Mods<RouteObject[]>
  nav: Mods<NavItem>
  widgets: Mods<Widget>
  profileSections: Mods<ProfileSection>
  headerSlots?: Mods<HeaderSlot>
}

export function sortByOrder<T extends { order: number }>(items: T[]): T[] {
  return [...items].sort((a, b) => a.order - b.order)
}

function byPath<T>(mods: Mods<T>): T[] {
  return Object.keys(mods)
    .sort()
    .map((k) => mods[k].default)
}

export function buildRegistry(input: RegistryInput) {
  return {
    featureRoutes: byPath(input.routes).flat(),
    navItems: sortByOrder(byPath(input.nav)),
    widgets: sortByOrder(byPath(input.widgets)),
    profileSections: sortByOrder(byPath(input.profileSections)),
    headerSlots: sortByOrder(byPath(input.headerSlots ?? {})),
  }
}

// Każda funkcja w features/<nazwa>/ dokłada się sama — bez edycji wspólnych plików.
const registry = buildRegistry({
  routes: import.meta.glob('./*/routes.tsx', { eager: true }) as Mods<RouteObject[]>,
  nav: import.meta.glob('./*/nav.ts', { eager: true }) as Mods<NavItem>,
  widgets: import.meta.glob('./*/widget.tsx', { eager: true }) as Mods<Widget>,
  profileSections: import.meta.glob('./*/profile-section.tsx', { eager: true }) as Mods<ProfileSection>,
  headerSlots: import.meta.glob('./*/header-slot.tsx', { eager: true }) as Mods<HeaderSlot>,
})

export const featureRoutes: RouteObject[] = registry.featureRoutes
export const navItems: NavItem[] = registry.navItems
export const widgets: Widget[] = registry.widgets
export const profileSections: ProfileSection[] = registry.profileSections
export const headerSlots: HeaderSlot[] = registry.headerSlots
