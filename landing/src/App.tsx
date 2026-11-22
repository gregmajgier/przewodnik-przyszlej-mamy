import { Logo } from './components/Logo'
import { ScrollRibbons } from './components/ScrollRibbons'
import { HeroIcons, LineIcon } from './components/HeroIcons'
import { Timeline } from './components/Timeline'
import { HowItWorks } from './components/HowItWorks'
import { Extras } from './components/Extras'
import { Calculator } from './components/Calculator'
import './App.css'

const APP_URL = import.meta.env.VITE_APP_URL ?? 'http://localhost:5173'

// Topics from the benefit catalog (backend/app/data/benefits_national.json).
const HELP_TOPICS = [
  { icon: 'document', title: 'Urlopy i zasiłki z ZUS' },
  { icon: 'coins', title: 'Świadczenie 800+' },
  { icon: 'bottle', title: 'Becikowe' },
  { icon: 'blocks', title: 'Aktywny rodzic i żłobek' },
  { icon: 'cap', title: 'Rekrutacja do przedszkola i szkoły' },
  { icon: 'backpack', title: 'Dobry Start na wyprawkę' },
  { icon: 'card', title: 'Karta Dużej Rodziny' },
  { icon: 'percent', title: 'Ulga prorodzinna w PIT' },
  { icon: 'thermometer', title: 'Zdrowie w ciąży i leki dla dzieci' },
  { icon: 'pin', title: 'Wsparcie z twojej gminy' },
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
          <iframe
            className="youtube-video"
            src="https://www.youtube-nocookie.com/embed/S3kinICctXM"
            title="Film mRodzina"
            loading="lazy"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            referrerPolicy="strict-origin-when-cross-origin"
            allowFullScreen
          />
        </section>

        <section className="section help-section">
          <h2>Pomożemy ci z:</h2>
          <ul className="topics">
            {HELP_TOPICS.map((t) => (
              <li className="topic" key={t.title}>
                <span className="topic-icon">
                  <LineIcon name={t.icon} size={34} />
                </span>
                {t.title}
              </li>
            ))}
          </ul>
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
