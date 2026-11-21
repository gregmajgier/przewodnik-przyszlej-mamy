import { Logo } from './components/Logo'
import './App.css'

const APP_URL = import.meta.env.VITE_APP_URL ?? 'http://localhost:5173'

function App() {
  return (
    <main>
      <section className="hero">
        <div className="hero-copy">
          <p>Mamo! Tato! Masz wiele na głowie...</p>
          <p className="pitch">
            Pozwól, że
            <span className="wordmark">
              <Logo className="wordmark-logo" />
              <span>Rodzina</span>
            </span>
            pomoże.
          </p>
          <a className="cta" href={APP_URL}>
            Zobacz, co możemy dla ciebie zrobić.
          </a>
        </div>
        <a className="scroll-hint" href="#info" aria-label="Przewiń w dół">
          <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <path d="M5 9l7 7 7-7" />
          </svg>
        </a>
      </section>
      <section id="info" className="info" />
    </main>
  )
}

export default App
