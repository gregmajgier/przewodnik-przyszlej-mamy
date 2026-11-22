import { describe, expect, it } from 'vitest'
import { decimalToNumber, sanitizeDecimalInput, sanitizeIntegerInput } from './numeric'

describe('numeric input helpers', () => {
  it('odrzuca litery i wartości ujemne', () => {
    expect(sanitizeDecimalInput('12abc')).toBeNull()
    expect(sanitizeDecimalInput('-12')).toBeNull()
    expect(sanitizeIntegerInput('12z')).toBeNull()
  })

  it('akceptuje liczby całkowite i dziesiętne', () => {
    expect(sanitizeDecimalInput('1922,50')).toBe('1922.50')
    expect(sanitizeIntegerInput('1922')).toBe('1922')
    expect(decimalToNumber('1922,50')).toBe(1922.5)
  })

  it('zwraca pustą wartość jako brak kwoty', () => {
    expect(sanitizeDecimalInput('')).toBe('')
    expect(decimalToNumber('')).toBeNull()
  })
})
