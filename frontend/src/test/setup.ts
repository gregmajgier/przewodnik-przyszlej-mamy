import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'

afterEach(() => {
  try {
    localStorage.clear()
  } catch {
    // brak localStorage w środowisku testowym
  }
})
