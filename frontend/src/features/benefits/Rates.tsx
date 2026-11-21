import { formatPln } from '../../lib/format'
import { useApi } from '../../lib/useApi'
import { Pill } from '../../ui/controls'
import type { Summary } from './types'

/** Fragment `GET /api/parametry` — pokazujemy tylko to, co jest w odpowiedzi. */
interface Parametry {
  zasilek_macierzynski_procent?: Record<string, number>
  swiadczenie_rodzicielskie_zl_mies?: number
  becikowe_zl?: number
  za_zyciem_zl?: number
}

const percent = (n: number) => `${String(n).replace('.', ',')}%`

/** Aktualne stawki (parametry ZUS) — sekcja na dole bazy świadczeń. */
export function Rates() {
  const params = useApi<Parametry>('/api/parametry')
  const summary = useApi<Summary>('/api/summary')
  const p = params.data
  const rows: [string, string][] = []
  const pct = p?.zasilek_macierzynski_procent
  if (pct?.macierzynski !== undefined) rows.push(['Zasiłek macierzyński', percent(pct.macierzynski)])
  if (pct?.rodzicielski !== undefined) rows.push(['Urlop rodzicielski', percent(pct.rodzicielski)])
  if (pct?.jednolity_wniosek_21_dni !== undefined) rows.push(['Jeden wniosek w 21 dni po porodzie', percent(pct.jednolity_wniosek_21_dni)])
  if (p?.swiadczenie_rodzicielskie_zl_mies !== undefined) rows.push(['Świadczenie rodzicielskie', `${formatPln(p.swiadczenie_rodzicielskie_zl_mies)} / mies.`])
  if (p?.becikowe_zl !== undefined) rows.push(['Becikowe', formatPln(p.becikowe_zl)])
  if (p?.za_zyciem_zl !== undefined) rows.push(['„Za życiem”', formatPln(p.za_zyciem_zl)])

  return (
    <section className="section" aria-labelledby="rates-h">
      <div className="section-head">
        <h2 id="rates-h">Stawki</h2>
        <Pill tone="green" dot>
          {summary.data?.parameters_label ?? 'Parametry ZUS 2026 – aktywne'}
        </Pill>
      </div>
      <div className="card rates">
        {rows.length === 0 ? (
          <p className="muted" style={{ margin: 0 }}>
            {params.error ? 'Stawki są chwilowo niedostępne.' : 'Wczytuję stawki…'}
          </p>
        ) : (
          <dl className="rates-list">
            {rows.map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>
    </section>
  )
}
