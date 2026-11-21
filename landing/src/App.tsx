import { Logo } from './components/Logo'
import { ScrollRibbons } from './components/ScrollRibbons'
import { HeroIcons } from './components/HeroIcons'
import { Timeline } from './components/Timeline'
import { HowItWorks } from './components/HowItWorks'
import { Extras } from './components/Extras'
import { Calculator } from './components/Calculator'
import './App.css'

const APP_URL = import.meta.env.VITE_APP_URL ?? 'http://localhost:5173'

// Topics from the benefit catalog (backend/app/data/benefits_national.json).
const HELP_TOPICS = [
  { badge: 'ZUS', title: 'Urlopy i zasiłki', text: 'Macierzyński, ojcowski, rodzicielski i L4 w ciąży.' },
  { badge: '800+', title: 'Świadczenie 800+', text: '800 zł co miesiąc na każde dziecko.' },
  { badge: '🍼', title: 'Becikowe', text: 'Jednorazowe wsparcie po narodzinach dziecka.' },
  { badge: '🧸', title: 'Aktywny rodzic', text: 'Na żłobek, nianię albo opiekę w domu.' },
  { badge: '🎒', title: 'Dobry Start', text: 'Co roku na wyprawkę do szkoły.' },
  { badge: '🏫', title: 'Żłobek, przedszkole, szkoła', text: 'Terminy rekrutacji i dokumenty.' },
  { badge: 'KDR', title: 'Karta Dużej Rodziny', text: 'Zniżki dla rodzin z trojgiem dzieci.' },
  { badge: 'PIT', title: 'Ulga prorodzinna', text: 'Zwrot podatku za każde dziecko.' },
  { badge: '📍', title: 'Wsparcie z twojej gminy', text: 'Lokalne programy, o których mało kto wie.' },
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
          <a href="#film">Film</a>
          <a href="#jak-to-dziala">Jak to działa</a>
          <a href="#kalkulator">Kalkulator</a>
          <a href="#cta">Zacznij</a>
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

        <HowItWorks />

        <Extras />

        <Calculator appUrl={APP_URL} />

        <Timeline />

        <section id="cta" className="final-cta">
          <HeroIcons variant="cta" />
          <a className="cta" href={APP_URL}>
            Sprawdź, co możemy dla ciebie zrobić.
          </a>
          <a className="support-link" href={`${APP_URL}/jaskolka`}>
            Potrzebujesz wsparcia po stracie dziecka lub w trudnej sytuacji? →
          </a>
        </section>
      </main>
    </>
  )
}

export default App
