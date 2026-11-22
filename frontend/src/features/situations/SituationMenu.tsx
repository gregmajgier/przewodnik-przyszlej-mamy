import { useState } from 'react'
import { api, ApiError } from '../../lib/api'
import type { Child } from '../../lib/types'
import { useFamilyMode } from './useFamilyMode'
import './situations.css'

const SITUATION_OPTIONS = [
  { kind: 'poronienie', label: 'Poronienie' },
  { kind: 'martwe-urodzenie', label: 'Martwe urodzenie' },
  { kind: 'smierc-dziecka', label: 'Śmierć dziecka' },
] as const

/**
 * Spokojna, niewyróżniona opcja „Zmiana sytuacji” na karcie dziecka. Jedno kliknięcie w pozycję zgłasza zmianę —
 * bez pól, uzasadnień i pytania „czy na pewno?” (cofnięcie jest możliwe przez kilka dni).
 */
export type LossKind = (typeof SITUATION_OPTIONS)[number]['kind']

export function SituationMenu({ child, onChanged }: { child: Child; onChanged: (kind: LossKind) => void | Promise<void> }) {
  const { refresh } = useFamilyMode()
  const [error, setError] = useState<string | null>(null)

  async function choose(kind: LossKind) {
    setError(null)
    try {
      await api(`/api/families/me/children/${child.id}/situation`, { method: 'POST', body: { kind } })
      await refresh()
      await onChanged(kind)
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Nie udało się zapisać zmiany. Spróbuj ponownie.')
    }
  }

  if (child.situation === 'loss') return null

  return (
    <details className="sit-menu">
      <summary aria-label={`Zmiana sytuacji: ${child.name}`}>Zmiana sytuacji</summary>
      <ul className="sit-menu-list">
        {SITUATION_OPTIONS.map((o) => (
          <li key={o.kind}>
            <button type="button" className="sit-menu-item" onClick={() => void choose(o.kind)}>
              {o.label}
            </button>
          </li>
        ))}
      </ul>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
    </details>
  )
}
