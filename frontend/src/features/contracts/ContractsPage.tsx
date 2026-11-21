import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { useSession } from '../../lib/session'
import ContractReview from './ContractReview'
import ContractUpload from './ContractUpload'
import RisksPanel from './RisksPanel'
import './contracts.css'
import { KIND_LABEL, MAX_FILES } from './types'
import type { Contract, ScanResult } from './types'

const money = new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN' })

function ContractCard({ c, mine, onDelete }: { c: Contract; mine: boolean; onDelete: () => void }) {
  return (
    <li className="card stack">
      <div>
        <h3>{c.employer_name}</h3>
        <p className="muted" style={{ margin: 0 }}>
          {c.kind ? KIND_LABEL[c.kind] : ''}
          {c.position ? ` · ${c.position}` : ''}
          {!mine && ' · dodana przez drugiego rodzica'}
        </p>
      </div>
      <dl className="facts">
        {c.start_date && (
          <>
            <dt>Od</dt>
            <dd>{formatDate(c.start_date)}</dd>
          </>
        )}
        <dt>Czas trwania</dt>
        <dd>
          {c.indefinite === false && c.end_date ? `określony, do ${formatDate(c.end_date)}` : 'nieokreślony'}
        </dd>
        {c.fte !== null && (
          <>
            <dt>Etat</dt>
            <dd>{c.fte}</dd>
          </>
        )}
        {c.gross_monthly !== null && (
          <>
            <dt>Brutto</dt>
            <dd>{money.format(c.gross_monthly)} miesięcznie</dd>
          </>
        )}
      </dl>
      {mine && (
        <div className="row">
          <button
            type="button"
            className="btn btn-danger"
            aria-label={`Usuń umowę ${c.employer_name}`}
            onClick={onDelete}
          >
            Usuń
          </button>
        </div>
      )}
    </li>
  )
}

/** Lista umów rodziny + dodawanie. `onboarding` = krok „Umowy” w /start/umowy (opcjonalny). */
export default function ContractsPage({ onboarding = false }: { onboarding?: boolean }) {
  const { user } = useSession()
  const [contracts, setContracts] = useState<Contract[] | null>(null)
  const [drafts, setDrafts] = useState<ScanResult[]>([])
  const [error, setError] = useState<string | null>(null)
  const [riskKey, setRiskKey] = useState(0)

  const load = useCallback(async () => {
    try {
      setContracts(await api<Contract[]>('/api/contracts'))
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Nie udało się pobrać umów.')
    }
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load()
  }, [load])

  const mineCount = (contracts ?? []).filter((c) => c.user_id === user?.id).length + drafts.length

  async function remove(id: string) {
    setError(null)
    try {
      await api(`/api/contracts/${id}`, { method: 'DELETE' })
      await load()
      setRiskKey((k) => k + 1)
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Nie udało się usunąć umowy.')
    }
  }

  return (
    <div className="stack" style={{ maxWidth: '48rem' }}>
      <h1>{onboarding ? 'Twoje umowy' : 'Umowy'}</h1>
      <p className="muted">
        Wgraj umowę (albo kilka — np. etat i zlecenie), a my wyciągniemy z niej dane do wniosków i sprawdzimy,
        czy czegoś nie grozi. Oboje rodzice widzą zatwierdzone dane, ale sam plik zostaje tylko u Ciebie —
        po odczytaniu go nie przechowujemy.
      </p>

      <ContractUpload
        slotsLeft={MAX_FILES - mineCount}
        onScanned={(r) => setDrafts((d) => [...d, r])}
      />

      {drafts.map((d) => (
        <ContractReview
          key={d.draft_id}
          draftId={d.draft_id}
          filename={d.filename}
          draft={d.draft}
          onConfirmed={() => {
            setDrafts((all) => all.filter((x) => x.draft_id !== d.draft_id))
            void load()
            setRiskKey((k) => k + 1)
          }}
          onDiscard={() => setDrafts((all) => all.filter((x) => x.draft_id !== d.draft_id))}
        />
      ))}

      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}

      <section className="stack" aria-labelledby="list-h">
        <h2 id="list-h">Zatwierdzone umowy</h2>
        {contracts === null ? (
          <p role="status">Ładowanie…</p>
        ) : contracts.length === 0 ? (
          <p className="muted">Nie dodano jeszcze żadnej umowy.</p>
        ) : (
          <ul className="contract-summary">
            {contracts.map((c) => (
              <ContractCard key={c.id} c={c} mine={c.user_id === user?.id} onDelete={() => remove(c.id)} />
            ))}
          </ul>
        )}
      </section>

      <section className="stack" aria-labelledby="risk-h">
        <h2 id="risk-h">Ostrzeżenia</h2>
        <RisksPanel key={riskKey} />
      </section>

      {onboarding && (
        <div className="row">
          <Link className="btn" to="/">
            Gotowe, przejdź dalej
          </Link>
          <Link to="/">Pomiń ten krok</Link>
        </div>
      )}
    </div>
  )
}
