import { useEffect, useRef } from 'react'

// Placeholder stages; real content/examples will be added later.
const STAGES = [
  { age: 'Przed narodzinami', title: 'Ciąża', text: 'Badania, formalności, przygotowania.' },
  { age: 'Narodziny', title: 'Urlop macierzyński', text: 'Wniosek, zasiłek, dokumenty.' },
  { age: 'Pierwsze miesiące', title: 'Urlop tacierzyński i rodzicielski', text: 'Podział urlopu między rodziców.' },
  { age: '1–3 lata', title: 'Żłobek', text: 'Zapisy, dofinansowanie.' },
  { age: '3–6 lat', title: 'Przedszkole', text: 'Rekrutacja i opłaty.' },
  { age: '7 lat', title: 'Szkoła podstawowa', text: 'Rekrutacja do szkół, zerówka.' },
  { age: '15 lat', title: 'Szkoła średnia', text: 'Wybór szkoły i rekrutacja.' },
  { age: '18 lat', title: 'Pełnoletność', text: 'Nowy etap: prawa i obowiązki.' },
]

// Vertical scroll drives a horizontal translation of the track while the
// stage stays pinned (position: sticky) in the viewport.
export function Timeline() {
  const section = useRef<HTMLElement>(null)
  const track = useRef<HTMLDivElement>(null)
  const fill = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let frame = 0
    const update = () => {
      frame = 0
      const s = section.current
      const t = track.current
      if (!s || !t) return
      const scrollable = s.offsetHeight - window.innerHeight
      const progress = scrollable > 0
        ? Math.min(1, Math.max(0, -s.getBoundingClientRect().top / scrollable))
        : 0
      const distance = Math.max(0, t.scrollWidth - t.parentElement!.clientWidth)
      t.style.transform = `translate3d(${-progress * distance}px,0,0)`
      if (fill.current) fill.current.style.transform = `scaleX(${progress})`
    }
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update)
    }
    update()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
      if (frame) cancelAnimationFrame(frame)
    }
  }, [])

  return (
    <section id="timeline" className="timeline" ref={section}>
      <div className="timeline-stage">
        <h2>Z Tobą od pierwszego dnia do pełnoletności</h2>
        <div className="timeline-viewport">
          <div className="timeline-track" ref={track}>
            <div className="timeline-line" aria-hidden="true" />
            {STAGES.map((s) => (
              <article className="timeline-item" key={s.title}>
                <span className="timeline-age">{s.age}</span>
                <span className="timeline-dot" aria-hidden="true" />
                <h3>{s.title}</h3>
                <p>{s.text}</p>
              </article>
            ))}
          </div>
        </div>
        <div className="timeline-progress" aria-hidden="true">
          <div className="timeline-progress-fill" ref={fill} />
        </div>
      </div>
    </section>
  )
}
