import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '../../lib/api'
import type { BenefitMatch } from './types'

/** Lista świadczeń z dopasowaniem + odpowiedzi tak/nie (zapisywane w profilu, dopasowanie przeliczane od razu). */
export function useBenefits(enabled = true) {
  const [items, setItems] = useState<BenefitMatch[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    api<BenefitMatch[]>('/api/benefits')
      .then((d) => !cancelled && setItems(d))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.detail : 'Nie udało się wczytać świadczeń.'))
    return () => {
      cancelled = true
    }
  }, [enabled])

  const answer = useCallback(async (benefitId: string, conditionId: string, value: boolean) => {
    setBusyId(benefitId)
    setError(null)
    try {
      const updated = await api<BenefitMatch>(`/api/benefits/${benefitId}/answers`, {
        method: 'POST',
        body: { condition_id: conditionId, answer: value },
      })
      setItems((prev) => prev?.map((m) => (m.benefit.id === benefitId ? updated : m)) ?? prev)
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Nie udało się zapisać odpowiedzi.')
    } finally {
      setBusyId(null)
    }
  }, [])

  return { items, error, busyId, answer }
}
