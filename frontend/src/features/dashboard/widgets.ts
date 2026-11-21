import { widgets } from '../registry'
import type { Widget } from '../registry'

/**
 * Widgety dashboardu z rejestru (każda funkcja dokłada `widget.tsx`), posortowane po `order`.
 * Funkcja zamiast stałej: rejestr importuje trasy dashboardu, więc odczyt musi nastąpić przy renderze.
 */
export function getDashboardWidgets(): Widget[] {
  return widgets
}
