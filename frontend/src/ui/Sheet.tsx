import { useEffect, useId, useRef } from 'react'
import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Icon } from './Icon'

interface Props {
  open: boolean
  onClose: () => void
  title: ReactNode
  /** Krótki tekst pod tytułem. */
  subtitle?: ReactNode
  children: ReactNode
  /** Przyciski przyklejone do dołu arkusza. */
  footer?: ReactNode
  /** Blokuje zamknięcie (np. w trakcie zapisu). */
  busy?: boolean
  size?: 'md' | 'lg'
}

/** Arkusz: na telefonie wysuwa się od dołu, na większym ekranie jest oknem na środku. */
export function Sheet({ open, onClose, title, subtitle, children, footer, busy = false, size = 'md' }: Props) {
  const titleId = useId()
  const panel = useRef<HTMLDivElement>(null)
  const lastFocus = useRef<Element | null>(null)

  useEffect(() => {
    if (!open) return
    lastFocus.current = document.activeElement
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const t = window.setTimeout(() => {
      const first = panel.current?.querySelector<HTMLElement>(
        'input, select, textarea, button:not([data-sheet-close]), [href], [tabindex]:not([tabindex="-1"])',
      )
      ;(first ?? panel.current)?.focus()
    }, 30)
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape' && !busy) onClose()
      if (e.key === 'Tab' && panel.current) {
        const items = panel.current.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])',
        )
        if (items.length === 0) return
        const first = items[0]
        const last = items[items.length - 1]
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      window.clearTimeout(t)
      document.body.style.overflow = prevOverflow
      document.removeEventListener('keydown', onKey)
      if (lastFocus.current instanceof HTMLElement) lastFocus.current.focus()
    }
  }, [open, busy, onClose])

  if (!open) return null

  return createPortal(
    <div className="sheet-root">
      <div className="sheet-backdrop" onClick={() => !busy && onClose()} aria-hidden="true" />
      <div
        ref={panel}
        className={`sheet sheet-${size}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <div className="sheet-grip" aria-hidden="true" />
        <header className="sheet-head">
          <div>
            <h2 id={titleId}>{title}</h2>
            {subtitle && <p className="muted sheet-sub">{subtitle}</p>}
          </div>
          <button
            type="button"
            className="icon-btn sheet-close"
            data-sheet-close
            onClick={onClose}
            disabled={busy}
            aria-label="Zamknij"
          >
            <Icon name="close" size={20} />
          </button>
        </header>
        <div className="sheet-body">{children}</div>
        {footer && <footer className="sheet-foot">{footer}</footer>}
      </div>
    </div>,
    document.body,
  )
}
