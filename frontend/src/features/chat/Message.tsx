import type { ReactNode } from 'react'
import type { ChatMessage } from './useChatStream'

const TOKEN_RE = /(\*\*[^*\n]+\*\*|https?:\/\/[^\s)<>]+)/g

/** Minimalny, bezpieczny renderer: **pogrubienie** i linki http(s); reszta jako zwykły tekst (bez HTML). */
function renderInline(line: string): ReactNode[] {
  return line.split(TOKEN_RE).map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) return <strong key={i}>{part.slice(2, -2)}</strong>
    if (/^https?:\/\//.test(part)) {
      const trimmed = part.replace(/[.,;:!?]+$/, '')
      const tail = part.slice(trimmed.length)
      return (
        <span key={i}>
          <a href={trimmed} target="_blank" rel="noopener noreferrer">
            {trimmed}
          </a>
          {tail}
        </span>
      )
    }
    return part
  })
}

const TOOL_LABEL: Record<string, string> = {
  szukaj_w_przepisach: 'Sprawdzam przepisy…',
  szukaj_w_sieci: 'Szukam w oficjalnych źródłach…',
  profil_rodziny: 'Sprawdzam dane Twojej rodziny…',
}

export function Message({ message, streaming }: { message: ChatMessage; streaming: boolean }) {
  const isUser = message.role === 'user'
  const lines = message.text.split('\n').filter((l) => l.trim() !== '')
  const waiting = !isUser && streaming && message.text === ''
  const lastTool = message.tools[message.tools.length - 1]

  return (
    <article
      className={`chat-msg ${isUser ? 'chat-msg-user' : 'chat-msg-ai'}`}
      aria-label={isUser ? 'Twoja wiadomość' : 'Odpowiedź mRodziny'}
    >
      {!isUser && <span className="chat-msg-badge">asystent AI</span>}
      {waiting && (
        <p className="muted chat-status" role="status">
          {lastTool ? (TOOL_LABEL[lastTool] ?? 'Sprawdzam…') : 'Myślę…'}
        </p>
      )}
      {lines.map((line, i) => (
        <p key={i}>{renderInline(line)}</p>
      ))}
      {message.sources.length > 0 && (
        <div className="chat-sources">
          <h3>Źródła</h3>
          <ul>
            {message.sources.map((s) => (
              <li key={`${s.url}-${s.title}`}>
                <a href={s.url} target="_blank" rel="noopener noreferrer">
                  {s.title}
                  <span className="chat-sr"> (otwiera się w nowej karcie)</span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  )
}
