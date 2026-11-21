import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError, BASE_URL, getToken } from '../../lib/api'

export interface ChatSource {
  kind: 'przepis' | 'web'
  article: string | null
  title: string
  url: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  sources: ChatSource[]
}

interface SseEvent {
  name: string
  data: Record<string, unknown>
}

const SESSION_KEY = 'chat.session'
const NETWORK_ERROR = 'Brak połączenia z serwerem. Sprawdź internet i spróbuj ponownie.'
const GENERIC_ERROR = 'Nie udało się uzyskać odpowiedzi. Spróbuj ponownie za chwilę.'

const TOOL_LABELS: Record<string, string> = {
  szukaj_w_przepisach: 'Szukam w przepisach…',
  szukaj_w_sieci: 'Szukam w sieci…',
  profil_rodziny: 'Sprawdzam dane Twojej rodziny…',
}

function readStoredSession(): string | null {
  try {
    return localStorage.getItem(SESSION_KEY)
  } catch {
    return null
  }
}

function storeSession(id: string | null): void {
  try {
    if (id) localStorage.setItem(SESSION_KEY, id)
    else localStorage.removeItem(SESSION_KEY)
  } catch {
    // brak localStorage — rozmowa działa, ale nie przetrwa odświeżenia
  }
}

function parseBlock(block: string): SseEvent | null {
  let name = 'message'
  const data: string[] = []
  for (const line of block.split('\n')) {
    if (line.startsWith('event: ')) name = line.slice(7).trim()
    else if (line.startsWith('data: ')) data.push(line.slice(6))
  }
  if (!data.length) return null
  try {
    return { name, data: JSON.parse(data.join('\n')) as Record<string, unknown> }
  } catch {
    return null
  }
}

/** Czyta strumień SSE (fetch + ReadableStream); składa zdarzenia także z kawałków przeciętych w środku. */
async function* readEvents(body: ReadableStream<Uint8Array>): AsyncGenerator<SseEvent> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
      let idx: number
      while ((idx = buffer.indexOf('\n\n')) >= 0) {
        const ev = parseBlock(buffer.slice(0, idx))
        buffer = buffer.slice(idx + 2)
        if (ev) yield ev
      }
    }
    const rest = parseBlock(buffer.trim())
    if (rest) yield rest
  } finally {
    reader.releaseLock()
  }
}

async function errorDetail(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') return body.detail
  } catch {
    // brak JSON — komunikat ogólny niżej
  }
  if (res.status === 401) return 'Sesja wygasła. Zaloguj się ponownie.'
  return GENERIC_ERROR
}

let counter = 0
const nextId = () => `m${Date.now().toString(36)}${(counter++).toString(36)}`

export function useChatStream() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [sending, setSending] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [activity, setActivity] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(() => readStoredSession())
  const sessionRef = useRef<string | null>(sessionId)
  const abortRef = useRef<AbortController | null>(null)
  const sendingRef = useRef(false)

  const setSession = useCallback((id: string | null) => {
    sessionRef.current = id
    setSessionId(id)
    storeSession(id)
  }, [])

  // Przywraca zapisaną rozmowę po odświeżeniu strony (404 = sesji już nie ma).
  useEffect(() => {
    const id = sessionRef.current
    if (!id) return
    let cancelled = false
    api<{ messages: { role: 'user' | 'assistant'; content: string; sources?: ChatSource[] }[] }>(
      `/api/chat/sessions/${id}`,
    )
      .then((s) => {
        if (cancelled) return
        setMessages(
          s.messages.map((m) => ({ id: nextId(), role: m.role, text: m.content, sources: m.sources ?? [] })),
        )
      })
      .catch((e) => {
        if (!cancelled && e instanceof ApiError && e.status === 404) setSession(null)
      })
    return () => {
      cancelled = true
    }
  }, [setSession])

  useEffect(() => () => abortRef.current?.abort(), [])

  const send = useCallback(
    async (raw: string) => {
      const text = raw.trim()
      if (!text || sendingRef.current) return
      sendingRef.current = true
      setSending(true)
      setNotice(null)
      setActivity('Myślę…')
      const assistantId = nextId()
      setMessages((m) => [...m, { id: nextId(), role: 'user', text, sources: [] }])
      const controller = new AbortController()
      abortRef.current = controller
      let started = false
      const upsertAssistant = (patch: (m: ChatMessage) => ChatMessage) =>
        setMessages((all) => {
          if (!all.some((m) => m.id === assistantId)) {
            return [...all, patch({ id: assistantId, role: 'assistant', text: '', sources: [] })]
          }
          return all.map((m) => (m.id === assistantId ? patch(m) : m))
        })
      try {
        const token = getToken()
        const res = await fetch(`${BASE_URL}/api/chat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'text/event-stream',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ session_id: sessionRef.current, message: text }),
          signal: controller.signal,
        })
        if (!res.ok || !res.body) {
          setNotice(await errorDetail(res))
          return
        }
        for await (const ev of readEvents(res.body)) {
          if (ev.name === 'session') setSession(String(ev.data.session_id))
          else if (ev.name === 'tool') setActivity(TOOL_LABELS[String(ev.data.name)] ?? 'Sprawdzam…')
          else if (ev.name === 'token') {
            started = true
            setActivity(null)
            upsertAssistant((m) => ({ ...m, text: m.text + String(ev.data.text ?? '') }))
          } else if (ev.name === 'sources') {
            upsertAssistant((m) => ({ ...m, sources: (ev.data.sources as ChatSource[]) ?? [] }))
          } else if (ev.name === 'error') {
            setNotice(String(ev.data.message ?? GENERIC_ERROR))
          }
        }
      } catch (e) {
        if (!(e instanceof DOMException && e.name === 'AbortError')) {
          setNotice(started ? GENERIC_ERROR : NETWORK_ERROR)
        }
      } finally {
        sendingRef.current = false
        setSending(false)
        setActivity(null)
        if (abortRef.current === controller) abortRef.current = null
      }
    },
    [setSession],
  )

  const reset = useCallback(() => {
    abortRef.current?.abort()
    sendingRef.current = false
    setMessages([])
    setNotice(null)
    setActivity(null)
    setSending(false)
    setSession(null)
  }, [setSession])

  return { messages, sending, notice, activity, sessionId, send, reset }
}
