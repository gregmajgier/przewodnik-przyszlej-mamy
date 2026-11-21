import type { FormEntry } from './types'

export interface ApplyAction {
  code: string
  label: string
}

const GENERIC = 'Złóż wniosek'

/** Do kogo trafia wniosek — po ludzku, bez wewnętrznych kodów typu URLOP-MAC-ROD. */
export function recipientLabel(code: string, form?: Pick<FormEntry, 'institution'>): string {
  const inst = (form?.institution ?? '').toLowerCase()
  if (inst.includes('pracodawc') || /^(urlop|rezygnacja)-/i.test(code)) return 'Wniosek dla pracodawcy'
  if (inst.includes('zus')) return 'Wniosek do ZUS'
  if (inst.includes('gmin') || inst.includes('mops') || inst.includes('ops')) return 'Wniosek do gminy'
  if (inst.includes('usc')) return 'Wniosek do urzędu stanu cywilnego'
  return GENERIC
}

/**
 * Przyciski „złóż wniosek” dla świadczenia: jeden na adresata (np. „dla pracodawcy” i „do ZUS”), z kolejnością
 * z danych świadczenia. Gdy dwa kody mają tego samego adresata, zostaje pierwszy — resztę da się wybrać w kreatorze.
 */
export function applyActions(codes: string[], forms: FormEntry[] = []): ApplyAction[] {
  const seen = new Set<string>()
  const out: ApplyAction[] = []
  for (const code of codes) {
    const label = recipientLabel(code, forms.find((f) => f.code === code))
    if (label !== GENERIC && seen.has(label)) continue
    seen.add(label)
    out.push({ code, label })
  }
  return out
}
