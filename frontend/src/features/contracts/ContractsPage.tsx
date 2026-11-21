import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { useSession } from '../../lib/session'
import ContractReview from './ContractReview'
import ContractUpload from './ContractUpload'
import RisksPanel from './RisksPanel'
import './contracts.css'
import { KIND_LABEL } from './types'
import type { Contract, ScanResult } from './types'

const money = new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN' })

export function ContractSummary({ c }: { c: Contract }) {
  const period = c.indefinite
    ? 'na czas nieokreślony'
    : c.end_date
      ? `do ${formatDate(c.end_date)}`
      : 'okres nieznany'
  return (
    <>
      <strong>{c.kind ? KIND_LABEL[c.kind] : 'Umowa'}</strong>, {c.employer_name}
      <br />
      <span className="muted">
        {c.position && `${c.position} · `}
        {c.gross_monthly !== null && `${money.format(c.gross_monthly)} brutto · `}
        {c.start_date && `od ${formatDate(c.start_date)}, `}
        {period}
      </span>
    </>
  )
}

/** Przepływ dodawania: wgraj -> sprawdź -> zatwierdź. Używany na /umowy i w onboardingu. */
export function AddContractFlow({ onAdded }: { onAdded: (c: Contract) => void }) {
  const [scan, setScan] = useState<ScanResult | null>(null)
  if (scan)
    return (
      <ContractReview
        scan={scan}
        onConfirmed={(c) => {
          setScan(null)
          onAdded(c)
        }}
        onCancel={() => setScan(null)}
      />
    )
  return <ContractUpload onScanned={setScan} />
}

export default function ContractsPage() {
  const { user, family } = useSession()
  const [contracts, setContracts] = useState<Contract[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [version, setVersion] = useState(0)

  const load = useCallback(() => {
    api<Contract[]>('/api/contracts')
      .then(setContracts)
      .catch((e) => setError(e instanceof ApiError ? e.detail : 'Nie udało się pobrać umów.'))
  }, [])

  useEffect(() => load(), [load])

  async function remove(id: string) {
    setError(null)
    try {
      await api(`/api/contracts/${id}`, { method: 'DELETE' })
      load()
      setVersion((v) => v + 1)
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Nie udało się usunąć umowy.')
    }
  }

  const nameOf = (uid: string) =>
    family?.members.find((m) => m.id === uid)?.name ?? (uid === user?.id ? user.name : 'Drugi rodzic')

  return (
    <div className="stack">
      <h1>Umowy</h1>
      <p className="muted">
        Z umów wiemy, jakie świadczenia Wam przysługują i co może je zablokować. Oboje rodzice widzą
        zatwierdzone dane, ale plik z umową widzi tylko osoba, która go wgrała.
      </p>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      <section className="card stack" aria-labelledby="contracts-h">
        <h2 id="contracts-h">Zatwierdzone umowy</h2>
        {contracts === null ? (
          <p role="status">Ładowanie…</p>
        ) : contracts.length === 0 ? (
          <p className="muted">Nie dodaliście jeszcze żadnej umowy.</p>
        ) : (
          <ul className="contract-list stack">
            {contracts.map((c) => (
              <li key={c.id} className="row" style={{ justifyContent: 'space-between' }}>
                <div>
                  <span className="muted">{nameOf(c.user_id)}: </span>
                  <ContractSummary c={c} />
                  {c.filename && <div className="muted">Plik: {c.filename}</div>}
                </div>
                {c.user_id === user?.id && (
                  <button className="btn btn-danger" type="button" onClick={() => remove(c.id)}>
                    Usuń
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
      <AddContractFlow
        onAdded={() => {
          load()
          setVersion((v) => v + 1)
        }}
      />
      <RisksPanel key={version} />
      <p className="muted">
        Dane z umów trafiają też do <Link to="/dane">Moich danych</Link>.
      </p>
    </div>
  )
}
