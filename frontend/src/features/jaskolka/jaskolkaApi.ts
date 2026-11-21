// Publiczne API /api/jaskolka/*. Celowo NIE używa lib/api.ts: ta ścieżka nigdy nie wysyła
// tokenu sesji (ani ciasteczek), nawet jeśli ktoś jest zalogowany w tej samej przeglądarce.

const BASE_URL: string = import.meta.env.VITE_API_URL ?? ''

export interface SituationSummary {
  id: string
  label: string
  intro: string
}

export type ChecklistKind = 'right' | 'document' | 'step'

export interface ChecklistItem {
  id: string
  title: string
  body: string
  kind: ChecklistKind
  deadline_text: string | null
  form_codes: string[]
  source_url: string
  verify: boolean
}

export interface SituationDetail extends SituationSummary {
  checklist: ChecklistItem[]
}

export interface Foundation {
  id: string
  name: string
  description: string
  url: string
  situations: string[]
  region: string | null
}

export class PublicApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'PublicApiError'
    this.status = status
  }
}

async function get<T>(path: string): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE_URL}${path}`, { credentials: 'omit' })
  } catch {
    throw new PublicApiError(0, 'Nie udało się połączyć z serwerem. Spróbuj ponownie za chwilę.')
  }
  let data: unknown = null
  try {
    data = await res.json()
  } catch {
    data = null
  }
  if (!res.ok) {
    const detail = (data as { detail?: unknown } | null)?.detail
    throw new PublicApiError(
      res.status,
      typeof detail === 'string' ? detail : 'Coś poszło nie tak. Spróbuj ponownie za chwilę.',
    )
  }
  return data as T
}

export const fetchSituations = () => get<SituationSummary[]>('/api/jaskolka/situations')
export const fetchSituation = (id: string) =>
  get<SituationDetail>(`/api/jaskolka/situations/${encodeURIComponent(id)}`)
export const fetchFoundations = (situation: string) =>
  get<Foundation[]>(`/api/jaskolka/foundations?situation=${encodeURIComponent(situation)}`)
