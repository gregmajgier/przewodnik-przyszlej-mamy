import { BrowserFrame } from './Frames'

const STEPS = [
  {
    title: 'Zaloguj się przez mObywatel',
    text: 'Dane z ZUS i mObywatela pobierzemy sami: kto jest w rodzinie, gdzie mieszkacie, jak pracujesz. Nie przepisujesz niczego, co urzędy już o tobie wiedzą.',
    shot: { src: 'step-1-analiza.webp', alt: 'Ekran „Sprawdzam, co Wam przysługuje” – mRodzina czyta dane z ZUS i mObywatela' },
  },
  {
    title: 'Zobacz, co ci przysługuje i dlaczego',
    text: 'Dostajesz listę świadczeń, ulg i urlopów dopasowanych do twojej rodziny. Przy każdym widzisz, dlaczego do was pasuje i jak je załatwić.',
    shot: { src: 'step-2-dlaczego.webp', alt: 'Karta zasiłku macierzyńskiego z sekcją „Dlaczego Wam pasuje”' },
  },
  {
    title: 'Wniosek wypełnia się sam',
    text: 'Większość pól uzupełniamy za ciebie. Ty sprawdzasz, dopisujesz brakujące dane i podpisujesz. Wniosek trafia do ZUS, gminy albo pracodawcy.',
    shot: { src: 'step-3-wniosek.webp', alt: 'Wniosek o zasiłek macierzyński z 15 polami wypełnionymi automatycznie' },
  },
  {
    title: 'Pilnujemy terminów',
    text: 'Wszystkie terminy całej rodziny w jednym kalendarzu, od ciąży aż do 18. urodzin dziecka. Drugi rodzic widzi to samo.',
    shot: { src: 'step-4-kalendarz.webp', alt: 'Kalendarz rodziny z terminami wniosków' },
  },
]

export function HowItWorks() {
  return (
    <section id="jak-to-dziala" className="section how-section">
      <h2>Jak to działa?</h2>
      <ol className="steps">
        {STEPS.map((s, i) => (
          <li className="step" key={s.title}>
            <div className="step-copy">
              <span className="step-number" aria-hidden="true">{i + 1}</span>
              <h3>{s.title}</h3>
              <p>{s.text}</p>
            </div>
            <BrowserFrame {...s.shot} width={760} height={700} />
          </li>
        ))}
      </ol>
    </section>
  )
}
