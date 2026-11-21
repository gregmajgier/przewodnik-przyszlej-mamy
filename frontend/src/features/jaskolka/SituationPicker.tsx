import { Link } from 'react-router-dom'
import type { SituationSummary } from './jaskolkaApi'

export function SituationPicker({ situations }: { situations: SituationSummary[] }) {
  return (
    <section aria-labelledby="jk-pick-title" className="jk-fade">
      <h1 id="jk-pick-title">W jakiej sytuacji jesteś?</h1>
      <p className="jk-lead">
        Wybierz to, co jest najbliżej. Pokażemy, co może ci przysługiwać, i o jakie dokumenty warto poprosić.
        Nie musisz niczego załatwiać dziś.
      </p>
      <ul className="jk-situations">
        {situations.map((s) => (
          <li key={s.id}>
            <Link to={`/jaskolka/${s.id}`} className="jk-situation">
              <span className="jk-situation-label">{s.label}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
