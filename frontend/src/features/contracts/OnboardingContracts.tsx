import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AddContractFlow, ContractSummary } from './ContractsPage'
import type { Contract } from './types'

/** Opcjonalny krok onboardingu „Umowy” (trasa /start/umowy). */
export default function OnboardingContracts() {
  const [added, setAdded] = useState<Contract[]>([])
  return (
    <div className="page page-narrow stack" style={{ paddingTop: '1.5rem' }}>
      <h1>Twoje umowy</h1>
      <p className="muted">
        Ten krok jest opcjonalny. Dodaj umowę, a sprawdzimy, czy nic nie zagraża Twoim świadczeniom
        — np. kończąca się umowa albo zlecenie bez ubezpieczenia chorobowego.
      </p>
      {added.length > 0 && (
        <ul className="card contract-list stack" aria-label="Dodane umowy">
          {added.map((c) => (
            <li key={c.id}>
              <ContractSummary c={c} />
            </li>
          ))}
        </ul>
      )}
      <AddContractFlow onAdded={(c) => setAdded((prev) => [...prev, c])} />
      <div className="row">
        <Link className="btn" to="/">
          {added.length ? 'Dalej' : 'Pomiń na razie'}
        </Link>
      </div>
    </div>
  )
}
