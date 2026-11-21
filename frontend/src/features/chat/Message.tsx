import { Fragment } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { ChatMessage } from './useChatStream'

// Linkujemy tylko adresy http(s) i wewnętrzny kreator wniosku; reszta tekstu jest zwykłym tekstem
// (bez dangerouslySetInnerHTML — odpowiedź modelu nie może wstrzyknąć znaczników).
const LINK_RE = /(https?:\/\/[^\s<>"]+|\/wnioski\/nowy\?form=[A-Za-z0-9_-]+)/g
const TRAILING = /[.,;:!?)\]]+$/

function inline(line: string): ReactNode[] {
  const out: ReactNode[] = []
  let last = 0
  for (const m of line.matchAll(LINK_RE)) {
    const start = m.index ?? 0
    const raw = m[0]
    const url = raw.replace(TRAILING, '')
    if (start > last) out.push(line.slice(last, start))
    if (url.startsWith('/')) {
      out.push(
        <Link key={start} to={url}>
          {url}
        </Link>,
      )
    } else {
      out.push(
        <a key={start} href={url} target="_blank" rel="noopener noreferrer">
          {url}
        </a>,
      )
    }
    out.push(raw.slice(url.length))
    last = start + raw.length
  }
  if (last < line.length) out.push(line.slice(last))
  return out
}

export function Message({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  const lines = message.text.split('\n')
  return (
    <article className={`chat-msg ${isUser ? 'chat-msg-user' : 'chat-msg-bot'}`} aria-label={isUser ? 'Ty' : 'mRodzina'}>
      <div className="chat-msg-body">
        {lines.map((line, i) =>
          line.trim() === '' ? null : (
            <p key={i}>
              <Fragment>{isUser ? line : inline(line)}</Fragment>
            </p>
          ),
        )}
      </div>
      {!isUser && message.sources.length > 0 && (
        <div className="chat-sources">
          <strong>Źródła</strong>
          <ul>
            {message.sources.map((s) => (
              <li key={`${s.article ?? ''}${s.url}`}>
                <a href={s.url} target="_blank" rel="noopener noreferrer">
                  {s.title}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  )
}
