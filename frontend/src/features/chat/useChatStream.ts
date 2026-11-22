import { useCallback, useEffect, useRef, useState } from 'react'
import { api, apiUrl, getToken } from '../../lib/api'

export const MAX_MESSAGE_CHARS = 2000

export interface ChatSource {
  kind: 'law' | 'web'
  title: string
  url: string
}

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  text: string
  sources: ChatSource[]
  /** nazwy narzędzi użytych w tej odpowiedzi (do statusu „sprawdzam przepisy…”) */
  tools: string[]
  failed?: boolean
}

export interface SseEvent {
  event: string
  data: unknown
}

/** Wydziela pełne zdarzenia SSE z bufora; niepełny ogon zwraca w `rest` (zdarzenie może przyjść w kawałkach). */
export function parseSse(buffer: string): { events: SseEvent[]; rest: string } {
  const blocks = buffer.replace(/\r\n/g, '\n').split('\n\n')
  const rest = blocks.pop() ?? ''
  const events: SseEvent[] = []
  for (const block of blocks) {
    let event = 'message'
    const dataLines: string[] = []
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''))
    }
    if (dataLines.length === 0) continue
    try {
      events.push({ event, data: JSON.parse(dataLines.join('\n')) })
    } catch {
      // uszkodzone zdarzenie pomijamy — reszta odpowiedzi nadal ma sens
    }
  }
  return { events, rest }
}

async function readDetail(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') return body.detail
  } catch {
    // brak JSON
  }
  if (res.status === 401) return 'Sesja wygasła. Zaloguj się ponownie.'
  return 'Nie udało się wysłać pytania. Spróbuj ponownie za chwilę.'
}

export function useChatStream({ onSession }: { onSession?: (id: string) => void } = {}) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  // zawsze najnowszy callback, bez przebudowy `send`/`open` przy każdym renderze
  const onSessionRef = useRef(onSession)
  useEffect(() => {
    onSessionRef.current = onSession
  })
  const [sending, setSending] = useState(false)
  /** spokojny komunikat o limitach (429) — nie jest błędem rozmowy */
  const [banner, setBanner] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const sessionId = useRef<string | null>(null)
  const nextId = useRef(1)
  const abort = useRef<AbortController | null>(null)
  const busy = useRef(false)

  useEffect(() => () => abort.current?.abort(), [])

  const patchLast = useCallback((fn: (m: ChatMessage) => ChatMessage) => {
    setMessages((prev) => (prev.length === 0 ? prev : [...prev.slice(0, -1), fn(prev[prev.length - 1])]))
  }, [])

  const send = useCallback(
    async (raw: string) => {
      const text = raw.trim()
      if (!text || busy.current) return
      if (text.length > MAX_MESSAGE_CHARS) {
        setError(`Wiadomość jest za długa (maksymalnie ${MAX_MESSAGE_CHARS} znaków).`)
        return
      }
      busy.current = true
      setSending(true)
      setBanner(null)
      setError(null)
      const controller = new AbortController()
      abort.current = controller
      setMessages((prev) => [
        ...prev,
        { id: nextId.current++, role: 'user', text, sources: [], tools: [] },
        { id: nextId.current++, role: 'assistant', text: '', sources: [], tools: [] },
      ])
      try {
        const headers: Record<string, string> = { 'Content-Type': 'application/json', Accept: 'text/event-stream' }
        const token = getToken()
        if (token) headers.Authorization = `Bearer ${token}`
        const res = await fetch(apiUrl('/api/chat'), {
          method: 'POST',
          headers,
          body: JSON.stringify({ session_id: sessionId.current, message: text }),
          signal: controller.signal,
        })
        if (!res.ok || !res.body) {
          const detail = await readDetail(res)
          if (res.status === 429) setBanner(detail)
          else setError(detail)
          setMessages((prev) => prev.slice(0, -1)) // usuń pustą odpowiedź; pytanie zostaje
          return
        }
        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        for (;;) {
          const { value, done } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const parsed = parseSse(buffer)
          buffer = parsed.rest
          for (const { event, data } of parsed.events) {
            const d = data as Record<string, unknown>
            if (event === 'token' && typeof d.text === 'string') {
              const piece = d.text
              patchLast((m) => ({ ...m, text: m.text + piece }))
            } else if (event === 'tool' && typeof d.name === 'string') {
              const name = d.name
              patchLast((m) => ({ ...m, tools: [...m.tools, name] }))
            } else if (event === 'sources' && Array.isArray(d.sources)) {
              patchLast((m) => ({ ...m, sources: d.sources as ChatSource[] }))
            } else if (event === 'done' && typeof d.session_id === 'string') {
              sessionId.current = d.session_id
              onSessionRef.current?.(d.session_id)
            } else if (event === 'error') {
              const message = typeof d.message === 'string' ? d.message : 'Coś poszło nie tak. Spróbuj ponownie.'
              setError(message)
              patchLast((m) => ({ ...m, failed: true }))
            }
          }
        }
      } catch (e) {
        if ((e as { name?: string }).name !== 'AbortError') {
          setError('Brak połączenia z serwerem. Sprawdź internet i spróbuj ponownie.')
          patchLast((m) => ({ ...m, failed: true }))
        }
      } finally {
        busy.current = false
        setSending(false)
      }
    },
    [patchLast],
  )

  /** Przerywa bieżącą odpowiedź (zostaje to, co już przyszło). */
  const stop = useCallback(() => {
    abort.current?.abort()
    busy.current = false
    setSending(false)
  }, [])

  /** Wczytuje zapisaną rozmowę (historia). */
  const open = useCallback(async (id: string): Promise<boolean> => {
    abort.current?.abort()
    busy.current = false
    setSending(false)
    setBanner(null)
    setError(null)
    try {
      const doc = await api<{ id: string; messages: { role: string; content: string; sources?: ChatSource[] }[] }>(
        `/api/chat/sessions/${encodeURIComponent(id)}`,
      )
      sessionId.current = doc.id
      onSessionRef.current?.(doc.id)
      setMessages(
        doc.messages
          .filter((m) => m.role === 'user' || m.role === 'assistant')
          .map((m) => ({
            id: nextId.current++,
            role: m.role as 'user' | 'assistant',
            text: m.content,
            sources: m.sources ?? [],
            tools: [],
          })),
      )
      return true
    } catch {
      setError('Nie udało się wczytać rozmowy.')
      return false
    }
  }, [])

  const reset = useCallback(() => {
    abort.current?.abort()
    busy.current = false
    sessionId.current = null
    setMessages([])
    setBanner(null)
    setError(null)
    setSending(false)
  }, [])

  return { messages, sending, banner, error, send, reset, stop, open, sessionId }
}
