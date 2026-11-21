import { api, apiBlob } from '../../lib/api'
import { formatDate } from '../../lib/format'
import type { Contract, EmploymentDocument } from './types'

export function listDocuments(): Promise<EmploymentDocument[]> {
  return api<EmploymentDocument[]>('/api/contracts/documents')
}

export function importDocument(id: string): Promise<Contract> {
  return api<Contract>(`/api/contracts/documents/${encodeURIComponent(id)}/import`, { method: 'POST' })
}

export function describeDocument(d: EmploymentDocument): string {
  const period = d.indefinite ? 'na czas nieokreślony' : d.end_date ? `do ${formatDate(d.end_date)}` : ''
  return [d.employer_name, d.position, `od ${formatDate(d.start_date)}${period ? ` ${period}` : ''}`]
    .filter(Boolean)
    .join(' · ')
}

/** Otwiera PDF umowy w nowej karcie. Okno otwieramy od razu (w geście użytkownika), żeby nie zablokował go bloker
 *  wyskakujących okien; plik pobieramy z tokenem i podstawiamy jako adres blob:. */
export async function openDocumentPdf(id: string): Promise<void> {
  const win = window.open('', '_blank')
  try {
    const blob = await apiBlob(`/api/contracts/documents/${encodeURIComponent(id)}/pdf`)
    const url = URL.createObjectURL(blob)
    if (win) win.location.href = url
    else window.location.assign(url)
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (e) {
    win?.close()
    throw e
  }
}
