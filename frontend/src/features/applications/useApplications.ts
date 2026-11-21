import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '../../lib/api'
import type { PillTone } from '../../ui/controls'
import type { MailThread, ThreadMessage } from './mailTypes'
import type { Application, AppStatus, Channel, FormsResponse } from './types'

/** Etapy na osi wniosku. */
export const STAGES = ['Wypełniony', 'Wysłany', 'Odebrany', 'Decyzja'] as const

export function stageOf(status: AppStatus): number {
  if (status === 'accepted' || status === 'rejected') return 3
  if (status === 'received' || status === 'more_info') return 2
  if (status === 'sent') return 1
  return 0
}

export const STATUS_TONE: Record<AppStatus, PillTone> = {
  draft: 'neutral',
  needs_input: 'amber',
  ready: 'blue',
  sent: 'blue',
  received: 'violet',
  more_info: 'amber',
  accepted: 'green',
  rejected: 'pink',
  cancelled: 'neutral',
}

export const CHANNEL_SHORT: Record<Channel, string> = {
  employer_email: 'PDF do pracodawcy',
  portal_agent: 'Formularz online',
  pdf_download: 'PDF do złożenia',
}

/** Krótkie, ludzkie tytuły wniosków (pełna nazwa urzędowa jest pod spodem). */
export const SHORT: Record<string, string> = {
  ZAM: 'Zasiłek macierzyński',
  'URLOP-MAC-ROD': 'Urlop macierzyński i rodzicielski',
  'URLOP-ROD': 'Urlop rodzicielski',
  'URLOP-OJC': 'Urlop ojcowski',
  'URLOP-UZUP': 'Uzupełniający urlop macierzyński',
  'URLOP-ROD-PRACA': 'Urlop rodzicielski z pracą',
  'REZYGNACJA-MAC': 'Rezygnacja z części urlopu',
  '800PLUS': 'Świadczenie 800+',
  'AKTYWNY-RODZIC': 'Aktywny rodzic',
  KDR: 'Karta Dużej Rodziny',
  'ZA-ZYCIEM': 'Świadczenie „Za życiem”',
  'ZAS-53': 'Zasiłek chorobowy',
  BECIKOWE: 'Becikowe',
  'SR-7': 'Świadczenie rodzicielskie',
  'SR-1': 'Zasiłek rodzinny',
}

export function isOpen(status: AppStatus): boolean {
  return status !== 'accepted' && status !== 'rejected' && status !== 'cancelled'
}

/** Ostatnia wiadomość w wątku wniosku (z Gmaila). */
export function latestMessage(thread: MailThread | undefined): ThreadMessage | undefined {
  if (!thread) return undefined
  return [...thread.messages].sort((a, b) => a.received_at.localeCompare(b.received_at)).at(-1)
}

/** Nadawca czytelnie: „kadry@kcuw.pl” → „kadry@kcuw.pl”, ZUS i urząd po nazwie. */
export function senderLabel(m: ThreadMessage): string {
  if (m.folder === 'sent') return 'Ty'
  const domain = m.from_addr.split('@')[1] ?? ''
  if (domain === 'zus.pl' || domain.endsWith('.zus.pl')) return 'ZUS'
  if (domain.startsWith('um.') || domain.includes('krakow.pl')) return 'Urząd Miasta'
  return m.from_addr
}

/** Wnioski rodziny + katalog formularzy + wątki poczty. `sync` pobiera nowe wiadomości z Gmaila. */
export function useApplications(enabled = true) {
  const [apps, setApps] = useState<Application[] | null>(null)
  const [catalog, setCatalog] = useState<FormsResponse | null>(null)
  const [threads, setThreads] = useState<MailThread[]>([])
  const [error, setError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [syncedAt, setSyncedAt] = useState<Date | null>(null)

  const load = useCallback(async () => {
    try {
      const [a, t] = await Promise.all([
        api<Application[]>('/api/applications'),
        api<MailThread[]>('/api/mail/threads').catch(() => [] as MailThread[]),
      ])
      setApps(a)
      setThreads(t)
      setError(null)
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Nie udało się wczytać wniosków.')
    }
  }, [])

  useEffect(() => {
    if (!enabled) return
    void load()
    api<FormsResponse>('/api/applications/forms')
      .then(setCatalog)
      .catch(() => undefined)
  }, [enabled, load])

  const sync = useCallback(async () => {
    setSyncing(true)
    try {
      await api('/api/mail/sync', { method: 'POST' })
      await load()
      setSyncedAt(new Date())
    } catch {
      // brak nowych danych z poczty nie blokuje listy wniosków
    } finally {
      setSyncing(false)
    }
  }, [load])

  const nameOf = useCallback((code: string) => catalog?.forms.find((f) => f.code === code)?.name ?? code, [catalog])
  const titleOf = useCallback((code: string) => SHORT[code] ?? nameOf(code), [nameOf])
  /** Tytuł z kalendarza („Wniosek ZAM”) z kodem zamienionym na krótką nazwę. */
  const humanize = useCallback(
    (text: string) => text.replace(/\b(?:Wniosek )?([A-Z0-9]+(?:-[A-Z0-9]+)+|ZAM|KDR|BECIKOWE|800PLUS)\b/g, (m, code: string) => SHORT[code] ?? m),
    [],
  )
  const threadOf = useCallback((id: string) => threads.find((t) => t.application.id === id), [threads])

  return { apps, catalog, threads, error, syncing, syncedAt, load, sync, nameOf, titleOf, humanize, threadOf }
}
