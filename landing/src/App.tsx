import { Logo } from './components/Logo'
import { ScrollRibbons } from './components/ScrollRibbons'
import { HeroIcons } from './components/HeroIcons'
import { Timeline } from './components/Timeline'
import './App.css'

const APP_URL = import.meta.env.VITE_APP_URL ?? 'http://localhost:5173'

// Placeholder topics; the final list will be decided later.
const HELP_TOPICS = [
  { badge: 'ZUS', title: 'ZUS', text: 'Zasiłki, urlopy, wnioski.' },
  { badge: '🎒', title: 'Rekrutacja do szkół', text: 'Terminy i dokumenty.' },
  { badge: '🍼', title: 'Żłobek i przedszkole', text: 'Zapisy i dofinansowania.' },
  { badge: '🏥', title: 'Zdrowie dziecka', text: 'Szczepienia i badania.' },
  { badge: '💶', title: 'Świadczenia', text: '800+ i inne wsparcie.' },
]

const FEATURES = [
  { title: 'Funkcja 1', text: 'Opis do uzupełnienia.' },
  { title: 'Funkcja 2', text: 'Opis do uzupełnienia.' },
  { title: 'Funkcja 3', text: 'Opis do uzupełnienia.' },
]

function App() {
  return (
    <>
      <header className="site-header">
        <a href="#top" className="header-logo" aria-label="mRodzina">
          <span className="wordmark header-wordmark">
            <Logo className="wordmark-logo" color="var(--bg)" animate={false} />
            <span className="wordmark-name">Rodzina</span>
          </span>
        </a>
        <nav>
          <a href="#film">O projekcie</a>
          <a href="#funkcje">Funkcje</a>
          <a href="#cta">Kontakt</a>
        </nav>
      </header>
      <main id="top">
        <section className="hero">
          <HeroIcons />
          <div className="hero-copy">
            <p>Mamo! Tato! Masz wiele na głowie...</p>
            <p className="pitch">
              <span className="wordmark">
                <Logo className="wordmark-logo" />
                <span className="wordmark-name">Rodzina</span>
              </span>
              pomoże.
            </p>
            <a className="cta" href={APP_URL}>
              Zobacz, co możemy dla ciebie zrobić.
            </a>
          </div>
          <a className="scroll-hint" href="#film" aria-label="Przewiń w dół, zobacz więcej">
            <span className="scroll-hint-text">Przewiń, żeby zobaczyć więcej</span>
            <span className="scroll-hint-arrow" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 9l7 7 7-7" />
              </svg>
            </span>
          </a>
        </section>

        <ScrollRibbons />

        <section id="film" className="section video-section">
          {/* Placeholder: replace with a YouTube <iframe> embed later. */}
          <div className="video-placeholder" role="img" aria-label="Miejsce na film z YouTube">
            <svg viewBox="0 0 24 24" width="72" height="72" fill="currentColor" aria-hidden="true">
              <path d="M8 5v14l11-7z" />
            </svg>
            <span>Tu pojawi się film z YouTube</span>
          </div>
        </section>

        <section className="section help-section">
          <h2>Pomożemy ci z:</h2>
          <div className="carousel">
            <div className="carousel-track">
              {[...HELP_TOPICS, ...HELP_TOPICS].map((t, i) => (
                <article
                  className="help-card"
                  key={i}
                  aria-hidden={i >= HELP_TOPICS.length ? true : undefined}
                >
                  <span className="help-badge">{t.badge}</span>
                  <h3>{t.title}</h3>
                  <p>{t.text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="funkcje" className="section features-section">
          <h2>Funkcje</h2>
          <div className="features-grid">
            {FEATURES.map((f) => (
              <article className="feature-card" key={f.title}>
                <h3>{f.title}</h3>
                <p>{f.text}</p>
              </article>
            ))}
          </div>
        </section>

        <Timeline />

        <section id="cta" className="final-cta">
          <HeroIcons variant="cta" />
          <a className="cta" href={APP_URL}>
            Sprawdź, co możemy dla ciebie zrobić.
          </a>
        </section>
      </main>
      <footer className="site-footer">
        <a className="support-link" href={`${APP_URL}/jaskolka`}>
          Potrzebujesz wsparcia po stracie dziecka lub w trudnej sytuacji? <span aria-hidden="true">→</span>
        </a>
      </footer>
    </>
  )
}

export default App
