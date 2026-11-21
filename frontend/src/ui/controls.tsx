import { useEffect, useId, useRef, useState } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { Icon } from './Icon'
import type { IconName } from './Icon'

/* ---------- Segmented: przełącznik kilku opcji ---------- */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: ReactNode; count?: number }[]
  value: T
  onChange: (v: T) => void
  label: string
}) {
  const index = Math.max(
    0,
    options.findIndex((o) => o.value === value),
  )
  return (
    <div className="segmented" role="tablist" aria-label={label} style={{ ['--n' as string]: options.length, ['--i' as string]: index }}>
      <span className="segmented-thumb" aria-hidden="true" />
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="tab"
          aria-selected={o.value === value}
          className="segmented-opt"
          onClick={() => onChange(o.value)}
        >
          {o.label}
          {o.count !== undefined && <span className="segmented-count">{o.count}</span>}
        </button>
      ))}
    </div>
  )
}

/* ---------- Toggle: przełącznik tak/nie ---------- */
export function Toggle({
  checked,
  onChange,
  label,
  description,
  disabled,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label: ReactNode
  description?: ReactNode
  disabled?: boolean
}) {
  const id = useId()
  return (
    <div className="toggle-row">
      <div className="toggle-text">
        <span id={`${id}-l`} className="toggle-label">
          {label}
        </span>
        {description && <span className="toggle-desc">{description}</span>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-labelledby={`${id}-l`}
        className="toggle"
        disabled={disabled}
        onClick={() => onChange(!checked)}
      >
        <span className="toggle-knob" />
      </button>
    </div>
  )
}

/* ---------- Avatar ---------- */
export type Tone = 'pink' | 'peach' | 'butter' | 'mint' | 'sky' | 'lilac'
export const TONES: Tone[] = ['peach', 'mint', 'sky', 'butter', 'lilac', 'pink']

export function Avatar({
  name,
  tone = 'pink',
  icon,
  size = 44,
  className,
}: {
  name: string
  tone?: Tone
  icon?: IconName
  size?: number
  className?: string
}) {
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join('')
  return (
    <span
      className={`avatar tone-${tone} ${className ?? ''}`}
      style={{ width: size, height: size, fontSize: size * 0.38 }}
      aria-hidden="true"
    >
      {icon ? <Icon name={icon} size={size * 0.5} /> : initials}
    </span>
  )
}

/* ---------- Status pill ---------- */
export type PillTone = 'neutral' | 'pink' | 'green' | 'amber' | 'blue' | 'violet'
export function Pill({ tone = 'neutral', children, dot }: { tone?: PillTone; children: ReactNode; dot?: boolean }) {
  return (
    <span className={`pill pill-${tone}`}>
      {dot && <span className="pill-dot" aria-hidden="true" />}
      {children}
    </span>
  )
}

/* ---------- Pasek postępu ---------- */
export function Progress({ value, label }: { value: number; label: string }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100)
  return (
    <div className="progress" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
      <span className="progress-fill" style={{ transform: `scaleX(${pct / 100})` }} />
    </div>
  )
}

/* ---------- Nagłówek podstrony ---------- */
export function PageHeader({
  title,
  eyebrow,
  back = '/',
  actions,
  children,
}: {
  title: ReactNode
  eyebrow?: ReactNode
  back?: string | false
  actions?: ReactNode
  children?: ReactNode
}) {
  const navigate = useNavigate()
  return (
    <header className="page-header rise">
      <div className="page-header-top">
        {back !== false && (
          <button
            type="button"
            className="icon-btn icon-btn-solid"
            aria-label="Wróć"
            onClick={() => (window.history.length > 1 ? navigate(-1) : navigate(back))}
          >
            <Icon name="arrowLeft" size={20} />
          </button>
        )}
        <div className="page-header-actions">{actions}</div>
      </div>
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <h1>{title}</h1>
      {children}
    </header>
  )
}

/* ---------- Select: własna lista wyboru ---------- */
export interface SelectOption {
  value: string
  label: string
  hint?: string
}

export function Select({
  label,
  value,
  options,
  onChange,
  placeholder = 'Wybierz…',
  id: idProp,
}: {
  label: string
  value: string
  options: SelectOption[]
  onChange: (v: string) => void
  placeholder?: string
  id?: string
}) {
  const autoId = useId()
  const id = idProp ?? autoId
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const root = useRef<HTMLDivElement>(null)
  const list = useRef<HTMLUListElement>(null)
  const selected = options.find((o) => o.value === value)

  useEffect(() => {
    if (!open) return
    function onDoc(e: MouseEvent) {
      if (root.current && !root.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  useEffect(() => {
    if (open) list.current?.querySelector<HTMLElement>(`[data-i="${active}"]`)?.scrollIntoView?.({ block: 'nearest' })
  }, [open, active])

  function openList() {
    setActive(Math.max(0, options.findIndex((o) => o.value === value)))
    setOpen(true)
  }

  function onKey(e: KeyboardEvent) {
    if (!open && (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault()
      openList()
      return
    }
    if (!open) return
    if (e.key === 'Escape') {
      e.preventDefault()
      setOpen(false)
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((a) => Math.min(options.length - 1, a + 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => Math.max(0, a - 1))
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      const o = options[active]
      if (o) onChange(o.value)
      setOpen(false)
    }
  }

  return (
    <div className="select" ref={root}>
      <span className="select-label" id={`${id}-label`}>
        {label}
      </span>
      <button
        type="button"
        id={id}
        className="select-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-labelledby={`${id}-label ${id}`}
        onClick={() => (open ? setOpen(false) : openList())}
        onKeyDown={onKey}
      >
        <span className={selected ? '' : 'select-placeholder'}>{selected?.label ?? placeholder}</span>
        <Icon name="chevronDown" size={18} className="select-chevron" />
      </button>
      {open && (
        <ul className="select-list" role="listbox" aria-labelledby={`${id}-label`} ref={list}>
          {options.map((o, i) => (
            <li
              key={o.value}
              role="option"
              data-i={i}
              aria-selected={o.value === value}
              className={`select-option ${i === active ? 'is-active' : ''}`}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                onChange(o.value)
                setOpen(false)
              }}
            >
              <span>
                {o.label}
                {o.hint && <span className="select-hint">{o.hint}</span>}
              </span>
              {o.value === value && <Icon name="check" size={18} />}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/* ---------- DateField: data jako DD.MM.RRRR (klawiatura numeryczna na telefonie) ---------- */
function isoToPl(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso)
  return m ? `${m[3]}.${m[2]}.${m[1]}` : ''
}
function plToIso(text: string): string | null {
  const m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(text)
  if (!m) return null
  const [, d, mo, y] = m
  const date = new Date(`${y}-${mo}-${d}T00:00:00`)
  if (Number.isNaN(date.getTime()) || date.getDate() !== Number(d) || date.getMonth() + 1 !== Number(mo)) return null
  return `${y}-${mo}-${d}`
}

export function DateField({
  label,
  value,
  onChange,
  id: idProp,
}: {
  label: string
  /** ISO „RRRR-MM-DD” albo pusty tekst */
  value: string
  onChange: (iso: string) => void
  id?: string
}) {
  const autoId = useId()
  const id = idProp ?? autoId
  const [text, setText] = useState(() => isoToPl(value))
  const [touched, setTouched] = useState(false)

  useEffect(() => {
    if (value === '' || plToIso(text) !== value) {
      setText(isoToPl(value))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value])

  function handle(raw: string) {
    const digits = raw.replace(/\D/g, '').slice(0, 8)
    let out = digits
    if (digits.length > 4) out = `${digits.slice(0, 2)}.${digits.slice(2, 4)}.${digits.slice(4)}`
    else if (digits.length > 2) out = `${digits.slice(0, 2)}.${digits.slice(2)}`
    setText(out)
    onChange(plToIso(out) ?? '')
  }

  const invalid = touched && text.length === 10 && plToIso(text) === null
  return (
    <label className="field" htmlFor={id}>
      {label}
      <span className="date-field">
        <input
          id={id}
          inputMode="numeric"
          autoComplete="off"
          placeholder="DD.MM.RRRR"
          value={text}
          aria-invalid={invalid || undefined}
          onBlur={() => setTouched(true)}
          onChange={(e) => handle(e.target.value)}
        />
        <Icon name="calendar" size={20} className="date-field-icon" />
      </span>
      {invalid && <span className="field-error">Sprawdź datę — taki dzień nie istnieje.</span>}
    </label>
  )
}
