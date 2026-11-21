import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api } from '../../lib/api'

export type ModeName = 'normal' | 'jaskolka'

/** Odpowiedź `GET /api/me/mode`. */
export interface FamilyMode {
  mode: ModeName
  since: string | null
  /** do kiedy można cofnąć zgłoszenie; `null` po upływie okna */
  undo_until: string | null
  child_id: string | null
}

export const NORMAL_MODE: FamilyMode = { mode: 'normal', since: null, undo_until: null, child_id: null }

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

/** Czy cofnięcie zgłoszenia jest jeszcze możliwe (okno `undo_until` nie minęło). */
export function canUndo(mode: FamilyMode, now: Date = new Date()): boolean {
  return mode.undo_until !== null && now.getTime() <= new Date(mode.undo_until).getTime()
}
