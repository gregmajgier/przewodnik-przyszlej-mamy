import { useRef, useState } from 'react'
import type { CSSProperties } from 'react'

const CODE_LEN = 8

/** Pole kodu zaproszenia do rodziny: jedno ukryte <input> + „kratki” na znaki. */
export function CodeInput({
  value,
  onChange,
  autoFocus = false,
  className = '',
  style,
}: {
  value: string
  onChange: (code: string) => void
  autoFocus?: boolean
  className?: string
  style?: CSSProperties
}) {
  const [focused, setFocused] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const boxes = Array.from({ length: Math.max(CODE_LEN, value.length) }, (_, i) => value[i] ?? '')

  return (
    <label className={`code-input-wrap ${className}`} style={style} onClick={() => input.current?.focus()}>
      <span className="sr-only">Kod zaproszenia</span>
      <input
        ref={input}
        value={value}
        onChange={(e) => onChange(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 16))}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        autoFocus={autoFocus}
        autoComplete="off"
        autoCapitalize="characters"
        spellCheck={false}
        maxLength={16}
        aria-label="Kod zaproszenia"
      />
      <span className="code-boxes" aria-hidden="true">
        {boxes.map((ch, i) => (
          <span key={i} className={`code-box ${focused && i === Math.min(value.length, boxes.length - 1) ? 'is-active' : ''}`}>
            {ch}
          </span>
        ))}
      </span>
    </label>
  )
}
