import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api, ApiError, getToken, setToken } from './api'
import type { FamilyView, User } from './types'

export interface SessionValue {
  user: User | null
  family: FamilyView | null
  token: string | null
  /** true, dopóki odtwarzamy sesję z zapisanego tokenu */
  loading: boolean
  /** Logowanie personą mObywatela. Zwraca użytkownika i jego rodzinę (jeśli ma). */
  login: (personaId: string) => Promise<{ user: User; family: FamilyView | null }>
  loginOfficial: (email: string, password: string) => Promise<User>
  logout: () => void
  /** Odświeża użytkownika i rodzinę (np. po utworzeniu rodziny lub akceptacji prośby). */
  refresh: () => Promise<void>
}

// eslint-disable-next-line react-refresh/only-export-components
export const SessionContext = createContext<SessionValue | null>(null)

async function loadFamily(user: User): Promise<FamilyView | null> {
  if (user.role !== 'parent') return null
  try {
    return await api<FamilyView>('/api/families/me')
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null
    throw e
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => getToken())
  const [user, setUser] = useState<User | null>(null)
  const [family, setFamily] = useState<FamilyView | null>(null)
  const [loading, setLoading] = useState<boolean>(() => getToken() !== null)

  const clear = useCallback(() => {
    setToken(null)
    setTokenState(null)
    setUser(null)
    setFamily(null)
  }, [])

  const refresh = useCallback(async () => {
    if (!getToken()) return
    try {
      const me = await api<User>('/api/me')
      setUser(me)
      setFamily(await loadFamily(me))
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) clear()
      else throw e
    }
  }, [clear])

  useEffect(() => {
    let cancelled = false
    async function restore() {
      if (getToken() === null) return
      try {
        await refresh()
      } catch {
        // błąd sieci: zostajemy niezalogowani, użytkownik może spróbować ponownie
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void restore()
    return () => {
      cancelled = true
    }
  }, [refresh])

  const startSession = useCallback(async (data: { token: string; user: User }) => {
    setToken(data.token)
    setTokenState(data.token)
    setUser(data.user)
    const fam = await loadFamily(data.user)
    setFamily(fam)
    return { user: data.user, family: fam }
  }, [])

  const login = useCallback(
    async (personaId: string) =>
      startSession(
        await api<{ token: string; user: User }>('/api/auth/mobywatel', {
          method: 'POST',
          body: { persona_id: personaId },
        }),
      ),
    [startSession],
  )

  const loginOfficial = useCallback(
    async (email: string, password: string) =>
      (
        await startSession(
          await api<{ token: string; user: User }>('/api/auth/official', {
            method: 'POST',
            body: { email, password },
          }),
        )
      ).user,
    [startSession],
  )

  const value = useMemo<SessionValue>(
    () => ({ user, family, token, loading, login, loginOfficial, logout: clear, refresh }),
    [user, family, token, loading, login, loginOfficial, clear, refresh],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useSession(): SessionValue {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error('useSession wymaga SessionProvider')
  return ctx
}
