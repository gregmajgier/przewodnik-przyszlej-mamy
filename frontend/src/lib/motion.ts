/** Czy użytkownik prosi o ograniczenie ruchu (`prefers-reduced-motion`). Bezpieczne tam, gdzie brak `matchMedia`. */
export function prefersReducedMotion(): boolean {
  try {
    return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
      : false
  } catch {
    return false
  }
}
