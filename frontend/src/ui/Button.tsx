import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Icon } from './Icon'
import type { IconName } from './Icon'

type Variant = 'primary' | 'secondary' | 'dark' | 'ghost' | 'white' | 'danger'

interface Common {
  variant?: Variant
  size?: 'md' | 'sm'
  block?: boolean
  /** Ikona na końcu, w osobnym kółku („przycisk w przycisku”). */
  icon?: IconName
  /** Ikona przed tekstem. */
  leading?: IconName
  className?: string
  children: ReactNode
}

type AsButton = Common & Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> & { to?: undefined; href?: undefined }
type AsLink = Common & { to: string; state?: unknown; href?: undefined; onClick?: () => void; 'aria-label'?: string }
type AsAnchor = Common & { href: string; to?: undefined; target?: string; rel?: string; download?: string }

export type ButtonProps = AsButton | AsLink | AsAnchor

function classes({ variant = 'primary', size = 'md', block, className }: Common): string {
  return [
    'btn',
    variant !== 'primary' && `btn-${variant}`,
    size === 'sm' && 'btn-sm',
    block && 'btn-block',
    className,
  ]
    .filter(Boolean)
    .join(' ')
}

function Inner({ icon, leading, children }: Pick<Common, 'icon' | 'leading' | 'children'>) {
  return (
    <>
      {leading && <Icon name={leading} size={19} />}
      <span>{children}</span>
      {icon && (
        <span className="btn-icon" aria-hidden="true">
          <Icon name={icon} size={17} stroke={2} />
        </span>
      )}
    </>
  )
}

export function Button(props: ButtonProps) {
  const cls = classes(props)
  if ('to' in props && props.to !== undefined) {
    const { to, state, onClick } = props
    return (
      <Link to={to} state={state} className={cls} onClick={onClick} aria-label={props['aria-label']}>
        <Inner {...props} />
      </Link>
    )
  }
  if ('href' in props && props.href !== undefined) {
    const { href, target, rel, download } = props
    return (
      <a href={href} className={cls} target={target} rel={rel} download={download}>
        <Inner {...props} />
      </a>
    )
  }
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const { variant, size, block, icon, leading, className, children, type = 'button', ...rest } = props as AsButton
  return (
    <button type={type} className={cls} {...rest}>
      <Inner icon={icon} leading={leading}>
        {children}
      </Inner>
    </button>
  )
}
