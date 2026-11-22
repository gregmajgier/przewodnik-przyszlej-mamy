/** Zostawia w polu kwotowym tylko nieujemną liczbę i jeden separator dziesiętny. */
export function sanitizeDecimalInput(raw: string): string | null {
  let value = raw.replace(/\s/g, '').replace(',', '.')
  if (value === '') return ''
  if (!/^\d*\.?\d*$/.test(value)) return null
  if ((value.match(/\./g) ?? []).length > 1) return null
  return value
}

export function decimalToNumber(raw: string): number | null {
  const value = sanitizeDecimalInput(raw)
  if (value === null || value === '' || value.endsWith('.')) return value === '' ? null : Number(value)
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

export function sanitizeIntegerInput(raw: string): string | null {
  return /^\d*$/.test(raw) ? raw : null
}
