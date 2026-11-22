import { useEffect, useMemo, useState } from 'react'
import { api, ApiError } from '../../lib/api'
import { Button } from '../../ui/Button'
import { Icon } from '../../ui/Icon'
import { Pill } from '../../ui/controls'
import { sanitizeDecimalInput, sanitizeIntegerInput } from '../../lib/numeric'
import './official.css'

interface ParameterRow {
  path: string
  value: number | string | boolean
  type: 'int' | 'float' | 'str' | 'bool'
}

interface ParametersResponse {
  base: ParameterRow[]
  active: ParameterRow[]
  overrides: Record<string, number | string | boolean>
  updated_at: string | null
  version: string
  simulation: boolean
}

function errText(error: unknown) {
  return error instanceof ApiError ? error.detail : 'Nie udało się pobrać parametrów.'
}

export default function NationalParameters() {
  const [data, setData] = useState<ParametersResponse | null>(null)
  const [values, setValues] = useState<Record<string, number | string | boolean>>({})
  const [query, setQuery] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)

  async function load() {
    setError(null)
    try {
      const result = await api<ParametersResponse>('/api/official/national-parameters')
      setData(result)
      setValues(Object.fromEntries(result.active.map((row) => [row.path, row.value])))
    } catch (e) {
      setError(errText(e))
    }
  }

  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    if (!saved) return
    const timer = window.setTimeout(() => setSaved(false), 4000)
    return () => window.clearTimeout(timer)
  }, [saved])

  const rows = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase('pl')
    return (data?.base ?? []).filter((row) => !needle || row.path.toLocaleLowerCase('pl').includes(needle))
  }, [data, query])

  function setValue(row: ParameterRow, raw: string) {
    let value: number | string | boolean = raw
    if (row.type === 'bool') value = raw === 'true'
    if (row.type === 'int') {
      const clean = sanitizeIntegerInput(raw)
      if (clean === null) return
      value = clean === '' ? 0 : Number(clean)
    }
    if (row.type === 'float') {
      const clean = sanitizeDecimalInput(raw)
      if (clean === null) return
      value = clean === '' ? 0 : Number(clean)
    }
    setValues((current) => ({ ...current, [row.path]: value }))
  }

  async function save() {
    setBusy(true)
    setError(null)
    try {
      const base = Object.fromEntries((data?.base ?? []).map((row) => [row.path, row.value]))
      const changed = Object.fromEntries(
        Object.entries(values).filter(([path, value]) => Object.is(base[path], value) === false),
      )
      await api<ParametersResponse>('/api/official/national-parameters', { method: 'PUT', body: { values: changed } })
      await load()
      setSaved(true)
    } catch (e) {
      setError(errText(e))
    } finally {
      setBusy(false)
    }
  }

  async function reset() {
    setBusy(true)
    setError(null)
    try {
      await api<ParametersResponse>('/api/official/national-parameters/reset', { method: 'POST' })
      await load()
      setSaved(true)
    } catch (e) {
      setError(errText(e))
    } finally {
      setBusy(false)
    }
  }

  if (!data) return <p role="status" className="page">Ładowanie parametrów…</p>

  return (
    <div className="page off-page">
      <section className="off-parameters-hero rise" aria-labelledby="parameters-h">
        <div>
          <p className="off-hero-eyebrow"><Icon name="scale" size={15} /> Silnik krajowy ZUS</p>
          <h1 id="parameters-h">Parametry i symulacja</h1>
          <p className="off-hero-lead">Zmiany wpływają na kalkulator i ocenę uprawnień w całej aplikacji. To oznaczony tryb demonstracyjny.</p>
        </div>
        <Pill tone="amber" dot>SYMULACJA · wersja {data.version}</Pill>
      </section>

      {error && <p role="alert" className="alert">{error}</p>}
      {saved && <p role="status" className="off-saved"><Icon name="checkCircle" size={18} /> Zapisano. Parametry są aktywne w tym środowisku.</p>}

      <div className="off-parameter-tools">
        <label className="off-search">
          <Icon name="search" size={18} />
          <span className="sr-only">Szukaj parametru</span>
          <input type="search" placeholder="Szukaj po ścieżce" value={query} onChange={(event) => setQuery(event.target.value)} />
        </label>
        <div>
          <Button type="button" variant="ghost" onClick={reset} disabled={busy}>Resetuj do źródła</Button>
          <Button type="button" icon="check" onClick={save} disabled={busy}>{busy ? 'Zapisywanie…' : 'Zapisz parametry'}</Button>
        </div>
      </div>

      <div className="off-parameter-table" role="region" aria-label="Lista parametrów krajowego silnika">
        <div className="off-parameter-head" aria-hidden="true">
          <span>Parametr</span><span>Wartość bazowa</span><span>Wartość aktywna</span>
        </div>
        {rows.map((row) => {
          const active = values[row.path] ?? row.value
          const baseChanged = active !== row.value
          return (
            <div className={`off-parameter-row${baseChanged ? ' is-changed' : ''}`} key={row.path}>
              <code title={row.path}>{row.path}</code>
              <span className="off-base-value">{String(row.value)}</span>
              {row.type === 'bool' ? (
                <select aria-label={`Wartość: ${row.path}`} value={String(active)} onChange={(event) => setValue(row, event.target.value)}>
                  <option value="true">Tak</option>
                  <option value="false">Nie</option>
                </select>
              ) : (
                <input
                  aria-label={`Wartość: ${row.path}`}
                  type={row.type === 'str' ? 'text' : 'number'}
                  step={row.type === 'float' ? '0.01' : '1'}
                  min={row.type === 'str' ? undefined : 0}
                  value={String(active)}
                  onChange={(event) => setValue(row, event.target.value)}
                />
              )}
            </div>
          )
        })}
        {rows.length === 0 && <p className="muted off-none">Brak parametrów pasujących do wyszukiwania.</p>}
      </div>
    </div>
  )
}
