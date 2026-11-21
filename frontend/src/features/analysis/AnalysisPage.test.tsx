import { act, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../lib/api'
import { routeApi } from '../../test/routeApi'
import type { Analysis } from '../benefits/types'
import AnalysisPage from './AnalysisPage'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

const ANALYSIS: Analysis = {
  steps: [
    { key: 'zus', label: 'Dane z ZUS', detail: 'umowa o pracę, podstawa 7 850 zł', status: 'done' },
    { key: 'contracts', label: 'Umowy', detail: '1', status: 'done' },
    { key: 'catalog', label: 'Przeglądamy świadczenia', detail: '22 krajowych, 0 lokalnych (Kraków, woj. małopolskie)', status: 'done' },
    { key: 'results', label: 'Wynik dopasowania', detail: 'pasuje do was: 7 · może przysługiwać: 3', status: 'done' },
    { key: 'deadlines', label: 'Terminy', detail: '1 termin w ciągu 30 dni', status: 'warning' },
  ],
  totals: { national: 22, local: 0, fits: 7, maybe: 3, no: 12 },
  estimated_annual_total: 21424,
  nearest_deadline: null,
}

function mockReducedMotion(reduced: boolean) {
  window.matchMedia = vi.fn().mockImplementation((q: string) => ({
    matches: reduced && q.includes('reduce'),
    media: q,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/analiza']}>
      <Routes>
        <Route path="/analiza" element={<AnalysisPage />} />
        <Route path="/" element={<p>Panel główny</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('AnalysisPage', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    mockReducedMotion(false)
  })
  afterEach(() => vi.useRealTimers())

  async function loaded() {
    routeApi({ 'GET /api/analysis': ANALYSIS })
    renderPage()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
  }

  it('odsłania kroki po kolei co ~700 ms, a bieżący pokazuje „⟳”', async () => {
    await loaded()
    expect(screen.getByText(/Dane z ZUS/)).toBeInTheDocument()
    expect(screen.queryByText(/Umowy/)).not.toBeInTheDocument()
    expect(screen.getByTestId('step-zus')).toHaveTextContent('⟳')

    await act(async () => {
      await vi.advanceTimersByTimeAsync(700)
    })
    expect(screen.getByTestId('step-zus')).toHaveTextContent('✓')
    expect(screen.getByTestId('step-contracts')).toHaveTextContent('⟳')
    expect(screen.queryByText(/Przeglądamy świadczenia/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /przejdź do panelu/i })).not.toBeInTheDocument()
  })

  it('na końcu: liczby z API, ostrzeżenie „⚠” i przycisk „Przejdź do panelu”', async () => {
    await loaded()
    for (let i = 0; i < 5; i++) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(700)
      })
    }
    expect(screen.getByText(/podstawa 7 850 zł/)).toBeInTheDocument()
    expect(screen.getByText(/22 krajowych/)).toBeInTheDocument()
    expect(screen.getByText(/pasuje do was: 7 · może przysługiwać: 3/)).toBeInTheDocument()
    expect(screen.getByTestId('step-deadlines')).toHaveTextContent('⚠')
    expect(screen.getByText(/21\s424\s*zł/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /przejdź do panelu/i })).toBeInTheDocument()
  })

  it('prefers-reduced-motion: wszystko od razu', async () => {
    mockReducedMotion(true)
    await loaded()
    expect(screen.getByTestId('step-deadlines')).toBeInTheDocument()
    expect(screen.getByText(/pasuje do was: 7/)).toBeInTheDocument()
    expect(screen.queryByText('⟳')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /przejdź do panelu/i })).toBeInTheDocument()
  })

  it('przycisk prowadzi do panelu', async () => {
    mockReducedMotion(true)
    await loaded()
    await act(async () => {
      screen.getByRole('button', { name: /przejdź do panelu/i }).click()
    })
    expect(screen.getByText('Panel główny')).toBeInTheDocument()
  })

  it('błąd API pokazuje komunikat i link do panelu', async () => {
    routeApi({ 'GET /api/analysis': new ApiError(404, 'Nie należysz jeszcze do żadnej rodziny.') })
    renderPage()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(screen.getByRole('alert')).toHaveTextContent('Nie należysz jeszcze do żadnej rodziny.')
  })
})
