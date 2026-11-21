import { Logo } from '../components/Logo'
import { Ribbons } from './Ribbons'
import './brand.css'

/** Ekran ładowania aplikacji: różowe tło, rysujące się logo i napis „Rodzina”, białe wstążki po bokach. */
export function Splash({ label = 'Ładuję mRodzinę…' }: { label?: string }) {
  return (
    <div className="splash" role="status" aria-live="polite">
      <Ribbons />
      <div className="splash-mark">
        <Logo className="splash-logo" color="#fff" duration={1300} />
        <span className="splash-word">Rodzina</span>
      </div>
      <span className="sr-only">{label}</span>
      <span className="splash-dots" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
    </div>
  )
}

/** Wordmark: logo-wstążka „m” + „Rodzina” (Sniglet). */
export function Wordmark({ light = false, className = '' }: { light?: boolean; className?: string }) {
  return (
    <span className={`wordmark ${light ? 'wordmark-light' : ''} ${className}`}>
      <Logo className="wordmark-logo" animate={false} />
      <span>Rodzina</span>
    </span>
  )
}
