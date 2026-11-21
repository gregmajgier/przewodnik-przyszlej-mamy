import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../lib/api'
import { ContractSummary } from './ContractsPage'
import type { Contract } from './types'

export default function ContractsOfParent({ userId }: { userId: string }) {
  const [contracts, setContracts] = useState<Contract[] | null>(null)

  useEffect(() => {
    let cancelled = false
    api<Contract[]>('/api/contracts')
      .then((all) => !cancelled && setContracts(all.filter((c) => c.user_id === userId)))
      .catch(() => !cancelled && setContracts([]))
    return () => {
      cancelled = true
    }
  }, [userId])

  if (contracts === null) return <p role="status">Ładowanie…</p>
  if (contracts.length === 0)
    return (
      <p className="muted">
        Brak zatwierdzonych umów. <Link to="/umowy">Dodaj umowę</Link>
      </p>
    )
  return (
    <ul className="contract-list stack">
      {contracts.map((c) => (
        <li key={c.id}>
          <ContractSummary c={c} />
        </li>
      ))}
    </ul>
  )
}
