import { useEffect, useMemo, useState } from 'react'
import { fetchFoundations } from './jaskolkaApi'
import type { Foundation } from './jaskolkaApi'

const ALL = ''

/** Komponent jest montowany z `key={situationId}`, więc stan zaczyna się od zera przy każdej sytuacji. */
export function Foundations({ situationId }: { situationId: string }) {
  const [items, setItems] = useState<Foundation[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [region, setRegion] = useState<string>(ALL)

  useEffect(() => {
    let cancelled = false
    fetchFoundations(situationId)
      .then((data) => {
        if (!cancelled) setItems(data)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Nie udało się wczytać listy.')
      })
    return () => {
      cancelled = true
    }
  }, [situationId])

  const regions = useMemo(
    () => [...new Set((items ?? []).map((f) => f.region).filter((r): r is string => r !== null))].sort(),
    [items],
  )

  // Organizacje ogólnopolskie (bez regionu) widać zawsze; wybór regionu dodaje te lokalne.
  const visible = (items ?? []).filter((f) => region === ALL || f.region === null || f.region === region)

  return (
    <section aria-labelledby="jk-found-title" className="jk-fade">
      <h2 id="jk-found-title">Gdzie można znaleźć wsparcie</h2>
      <p className="jk-lead">
        Fundacje, hospicja i telefony wsparcia. Warto sprawdzić na ich stronach, jaką pomoc oferują teraz.
      </p>

      {error && (
        <p role="alert" className="jk-note">
          {error}
        </p>
      )}
      {items === null && !error && <p role="status">Wczytywanie…</p>}

      {items !== null && items.length === 0 && (
        <p role="status" className="jk-note">
          Nie mamy jeszcze organizacji dla tej sytuacji. Zadzwoń pod 116 123: bezpłatnie i całodobowo.
        </p>
      )}

      {items !== null && items.length > 0 && regions.length > 0 && (
        <div className="jk-field">
          <label htmlFor="jk-region">Gdzie mieszkasz</label>
          <select id="jk-region" value={region} onChange={(e) => setRegion(e.target.value)}>
            <option value={ALL}>Pokaż wszystkie</option>
            {regions.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </div>
      )}

      {items !== null && items.length > 0 && visible.length === 0 && (
        <p role="status" className="jk-note">
          Nie ma organizacji dla wybranego miejsca. Pokaż wszystkie albo zadzwoń pod 116 123.
        </p>
      )}

      <ul className="jk-found-list">
        {visible.map((f) => (
          <li key={f.id} className="jk-card">
            <h3>
              <a href={f.url} target="_blank" rel="noopener noreferrer">
                {f.name}
                <span className="jk-sr"> (otwiera się w nowej karcie)</span>
              </a>
            </h3>
            <p>{f.description}</p>
            {f.region && <p className="jk-region">{f.region}</p>}
          </li>
        ))}
      </ul>
    </section>
  )
}
