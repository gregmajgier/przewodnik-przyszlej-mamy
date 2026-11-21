// Typy odpowiadające backend/app/models/contract.py (plan 04).

export type ContractKind = 'employment' | 'mandate' | 'jdg'

export interface ContractDraft {
  kind: ContractKind | null
  employer_name: string | null
  employer_address: string | null
  employer_email: string | null
  position: string | null
  fte: number | null
  gross_monthly: number | null
  start_date: string | null
  end_date: string | null
  indefinite: boolean | null
  voluntary_sickness: boolean | null
  missing: string[]
}

export interface Contract extends ContractDraft {
  id: string
  user_id: string
  family_id: string
  filename: string | null
  source_doc_id?: string | null
  confirmed: boolean
  created_at: string
}

/** Umowa z e-teczki pracodawcy, przypisana do zalogowanego rodzica (GET /api/contracts/documents). */
export interface EmploymentDocument {
  id: string
  title: string
  filename: string
  kind: ContractKind
  employer_name: string
  position: string | null
  fte: number | null
  gross_monthly: number | null
  start_date: string
  end_date: string | null
  indefinite: boolean
  voluntary_sickness: boolean | null
  contract_id: string | null
}

export interface ScanResult {
  draft_id: string
  draft: ContractDraft
  filename: string
}

export interface Risk {
  id: string
  severity: 'info' | 'medium' | 'high'
  title: string
  explanation: string
  action: string | null
  deadline: string | null
  user_id: string
  source_ref: string
}

export const KIND_LABEL: Record<ContractKind, string> = {
  employment: 'Umowa o pracę',
  mandate: 'Umowa zlecenie',
  jdg: 'Działalność gospodarcza',
}
