import type { Widget } from '../registry'

// Te same pliki `features/*/widget.tsx`, które wykrywa registry. Dashboard czyta je tu bezpośrednio
// (a nie z registry.ts), bo registry importuje trasy dashboardu — import z registry byłby cykliczny.
const modules = import.meta.glob('../*/widget.tsx', { eager: true }) as Record<string, { default: Widget }>

export const dashboardWidgets: Widget[] = Object.keys(modules)
  .sort()
  .map((k) => modules[k].default)
  .sort((a, b) => a.order - b.order)
