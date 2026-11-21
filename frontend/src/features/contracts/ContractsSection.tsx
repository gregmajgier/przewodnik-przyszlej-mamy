import { useEffect, useState } from 'react'
import { api } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { KIND_LABEL } from './types'
import type { Contract } from './types'

/** Zatwierdzone umowy danego rodzica w „Moich danych”. */
export default function ContractsSection({ userId }: { userId: string; userName: string }) {
  const [items, setItems] = useState<Contract[] | null>(null)

  useEffect(() => {
    let cancelled = false
    api<Contract[]>('/api/contracts')
      .then((all) => !cancelled && setItems(all.filter((c) => c.user_id === userId)))
      .catch(() => !cancelled && setItems([]))
    return () => {
      cancelled = true
    }
  }, [userId])

  if (items === null) return <p role="status">Ładowanie…</p>
  if (items.length === 0) return <p className="muted">Tutaj pojawią się dane z zatwierdzonych skanów umów.</p>
  return (
    <ul style={{ margin: 0, paddingLeft: '1.1rem' }}>
      {items.map((c) => (
        <li key={c.id}>
          {c.employer_name} <span className="muted">— {c.kind ? KIND_LABEL[c.kind].toLowerCase() : ''}
          {c.start_date ? `, od ${formatDate(c.start_date)}` : ''}</span>
        </li>
      ))}
    </ul>
  )
}
