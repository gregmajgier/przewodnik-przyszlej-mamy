import { BrowserFrame, PhoneFrame } from './Frames'

const EXTRAS = [
  {
    title: 'Zapytaj mRodzinę',
    text: 'Pytaj o urlop, żłobek czy szkołę. Odpowiadamy prostym językiem i zawsze pokazujemy przepis, na którym się opieramy.',
    shot: { src: 'extra-czat.webp', alt: 'Czat „Zapytaj mRodzinę” odpowiada na pytanie o pierwszy miesiąc po porodzie' },
  },
  {
    title: 'Powiadomienia SMS i e-mail',
    text: 'Nic ważnego ci nie umknie. Napiszemy SMS-a i maila, gdy zbliża się termin, urząd odpowie na wniosek albo pojawi się nowe świadczenie dla was.',
    shot: { src: 'extra-statusy.webp', alt: 'Status wniosku i korespondencja z pracodawcą aktualizowane automatycznie' },
  },
  {
    title: 'Wspólne konto rodziny',
    text: 'Zaproś drugiego rodzica kodem. Oboje widzicie sprawy dzieci, a każde z was prowadzi swoje urlopy i wnioski.',
    shot: { src: 'extra-rodzina.webp', alt: 'Ekran rodziny z kodem zaproszenia dla drugiego rodzica' },
  },
]

// Sample local benefits seeded for the demo (backend/app/data/benefits_local_sample.json).
const LOCAL_EXAMPLES = [
  { name: 'Krakowska Karta Rodzinna 3+', unit: 'Gmina Kraków' },
  { name: 'Dopłata do niepublicznego żłobka', unit: 'Gmina Kraków' },
  { name: 'Bon dla rodzin wielodzietnych', unit: 'Województwo małopolskie' },
]

function PinIcon() {
  return (
    <svg viewBox="0 0 24 24" width="56" height="56" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z" />
      <circle cx="12" cy="9.5" r="2.5" />
    </svg>
  )
}

export function Extras() {
  return (
    <section className="section extras-section">
      <h2>A do tego…</h2>
      <div className="extras-grid">
        {EXTRAS.map((e) => (
          <article className="extra-card" key={e.title}>
            <BrowserFrame {...e.shot} width={720} height={640} />
            <h3>{e.title}</h3>
            <p>{e.text}</p>
          </article>
        ))}
        <article className="extra-card">
          <div className="browser" aria-hidden="true">
            <div className="browser-bar">
              <span />
              <span />
              <span />
            </div>
            <div className="extra-visual">
              <PinIcon />
              <p className="local-label">Na przykład dla rodziny z Krakowa:</p>
              <ul className="local-list">
                {LOCAL_EXAMPLES.map((l) => (
                  <li key={l.name}>
                    <strong>{l.name}</strong>
                    <span>{l.unit}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <h3>Świadczenia z twojej gminy</h3>
          <p>Oprócz programów krajowych pokazujemy lokalne wsparcie z twojej gminy i województwa, o którym często trudno się dowiedzieć.</p>
        </article>
      </div>

      <div className="mobile-band">
        <div className="mobile-copy">
          <h2>mRodzina także w telefonie</h2>
          <p>
            Mamy też aplikację mobilną. Wszystkie sprawy rodziny masz w kieszeni, a powiadomienia o terminach
            przychodzą prosto na telefon.
          </p>
        </div>
        <PhoneFrame src="mobile-dashboard.webp" alt="Panel główny mRodziny na telefonie" width={780} height={1688} />
      </div>
    </section>
  )
}
