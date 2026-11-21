import { useState } from 'react'
import type { ReactNode } from 'react'
import { Logo } from '../../components/Logo'
import { Icon } from '../../ui/Icon'
import type { ChatMessage } from './useChatStream'

const TOKEN_RE = /(\*\*[^*\n]+\*\*|https?:\/\/[^\s)<>]+)/g

/** Bezpieczny renderer: **pogrubienie** i linki http(s); reszta jako zwykły tekst (bez HTML). */
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

/** Akapity, listy punktowane/numerowane i nagłówki „###”. */
function renderBlocks(text: string): ReactNode[] {
  const lines = text.split('\n')
  const out: ReactNode[] = []
  let list: { ordered: boolean; items: string[] } | null = null
  const flush = () => {
    if (!list) return
    const items = list.items.map((it, i) => <li key={i}>{renderInline(it)}</li>)
    out.push(list.ordered ? <ol key={out.length}>{items}</ol> : <ul key={out.length}>{items}</ul>)
    list = null
  }
  for (const raw of lines) {
    const line = raw.trimEnd()
    if (line.trim() === '') {
      flush()
      continue
    }
    const bullet = /^\s*[-*•]\s+(.*)$/.exec(line)
    const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line)
    const heading = /^#{1,4}\s+(.*)$/.exec(line)
    if (bullet || numbered) {
      const ordered = !!numbered
      if (!list || list.ordered !== ordered) {
        flush()
        list = { ordered, items: [] }
      }
      list.items.push((bullet ?? numbered)![1])
      continue
    }
    flush()
    if (heading) out.push(<h4 key={out.length}>{renderInline(heading[1])}</h4>)
    else out.push(<p key={out.length}>{renderInline(line)}</p>)
  }
  flush()
  return out
}

const TOOL_LABEL: Record<string, string> = {
  szukaj_w_przepisach: 'Sprawdzam przepisy',
  szukaj_w_sieci: 'Szukam w oficjalnych źródłach',
  profil_rodziny: 'Sprawdzam dane Twojej rodziny',
}

export function Message({ message, streaming }: { message: ChatMessage; streaming: boolean }) {
  const [copied, setCopied] = useState(false)
  const isUser = message.role === 'user'
  const waiting = !isUser && streaming && message.text === ''
  const lastTool = message.tools[message.tools.length - 1]

  if (isUser) {
    return (
      <article className="msg msg-user" aria-label="Twoja wiadomość">
        <div className="msg-bubble">{message.text}</div>
      </article>
    )
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(message.text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
    }
  }

  return (
    <article className={`msg msg-ai ${message.failed ? 'is-failed' : ''}`} aria-label="Odpowiedź mRodziny">
      <span className="msg-avatar" aria-hidden="true">
        <Logo className="msg-logo" color="#fff" animate={false} />
      </span>
      <div className="msg-content">
        {waiting && (
          <p className="msg-status" role="status">
            <span className="shimmer-text">{lastTool ? (TOOL_LABEL[lastTool] ?? 'Sprawdzam') : 'Myślę'}</span>
            <span className="typing" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
          </p>
        )}
        <div className="msg-text">{renderBlocks(message.text)}</div>
        {message.sources.length > 0 && (
          <div className="msg-sources">
            <span className="msg-sources-h">Źródła</span>
            <ul>
              {message.sources.map((s) => (
                <li key={`${s.url}-${s.title}`}>
                  <a href={s.url} target="_blank" rel="noopener noreferrer" className="source-chip">
                    <Icon name={s.kind === 'law' ? 'scale' : 'globe'} size={15} />
                    <span>{s.title}</span>
                    <span className="sr-only"> (otwiera się w nowej karcie)</span>
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}
        {!streaming && message.text && (
          <div className="msg-actions">
            <button type="button" className="icon-btn msg-action" onClick={() => void copy()} aria-label="Kopiuj odpowiedź">
              <Icon name={copied ? 'check' : 'copy'} size={17} />
            </button>
          </div>
        )}
      </div>
    </article>
  )
}
