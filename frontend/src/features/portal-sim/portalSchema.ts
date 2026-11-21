import type { FieldType, PortalKind } from '../applications/types'
import type { FieldValue } from './agentBridge'

export interface PortalField {
  id: string
  label: string
  type: FieldType
  required: boolean
  choices: string[] | null
  default?: unknown
}

export interface PortalSchema {
  portal_id: string
  title: string
  kind: PortalKind
  form_code: string
  fields: PortalField[]
}

const MAX_TEXT = 500
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/

/** Wartość od agenta zgodna z typem pola albo `null` (wtedy pole zostaje nietknięte). */
export function coerceFill(field: PortalField, value: FieldValue): FieldValue | null {
  switch (field.type) {
    case 'bool':
      return typeof value === 'boolean' ? value : null
    case 'choice':
      return typeof value === 'string' && (field.choices ?? []).includes(value) ? value : null
    case 'date':
      return typeof value === 'string' && DATE_RE.test(value) ? value : null
    default:
      return typeof value === 'string' && value.length <= MAX_TEXT ? value : null
  }
}

export function initialValues(schema: PortalSchema): Record<string, FieldValue> {
  const out: Record<string, FieldValue> = {}
  for (const f of schema.fields) {
    out[f.id] = f.type === 'bool' ? f.default === true : typeof f.default === 'string' ? f.default : ''
  }
  return out
}
