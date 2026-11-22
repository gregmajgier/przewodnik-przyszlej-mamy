import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api } from '../../lib/api'

export type ModeName = 'normal' | 'jaskolka'

/** Odpowiedź `GET /api/me/mode`. */
export interface FamilyMode {
  mode: ModeName
  since: string | null
  child_id: string | null
  /** czy zgłoszenie można cofnąć; w trybie jaskółki zawsze tak (bez limitu czasu) */
  can_undo: boolean
}

export const NORMAL_MODE: FamilyMode = { mode: 'normal', since: null, child_id: null, can_undo: false }

export interface FamilyModeValue {
  mode: FamilyMode
  /** pobiera tryb ponownie (po zgłoszeniu, cofnięciu, wyjściu z trybu) */
  refresh: () => Promise<void>
}

export const FamilyModeContext = createContext<FamilyModeValue>({
  mode: NORMAL_MODE,
  refresh: async () => {},
})

/** Stan trybu rodziny pobierany z `/api/me/mode`. Używa go AppShell i udostępnia przez `FamilyModeContext`. */
export function useFamilyModeState(enabled: boolean): FamilyModeValue {
  const [mode, setMode] = useState<FamilyMode>(NORMAL_MODE)

  const refresh = useCallback(async () => {
    if (!enabled) return
    try {
      setMode(await api<FamilyMode>('/api/me/mode'))
    } catch {
      // błąd sieci nie przełącza trybu: zostaje ostatnio znany
    }
  }, [enabled])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh()
  }, [refresh])

  return { mode: enabled ? mode : NORMAL_MODE, refresh }
}

export function useFamilyMode(): FamilyModeValue {
  return useContext(FamilyModeContext)
}

/** Czy zgłoszenie można cofnąć (backend: zawsze, dopóki rodzina jest w trybie jaskółki). */
export function canUndo(mode: FamilyMode): boolean {
  return mode.mode === 'jaskolka' && mode.can_undo
}
