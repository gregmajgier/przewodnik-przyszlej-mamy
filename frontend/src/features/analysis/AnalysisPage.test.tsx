import { act, fireEvent, screen } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { FamilyView } from '../../lib/types'
import { ANNA, makeSession, renderWithSession } from '../../test/utils'
import { routeApi } from '../../test/routeApi'
import type { Analysis } from '../benefits/types'
import AnalysisPage, { STEP_MS } from './AnalysisPage'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

const FAMILY = {
  family: { id: 'f1', name: 'Nowak', owner_id: ANNA.id, member_ids: [ANNA.id], invite_code: null, invite_expires_at: null },
  members: [ANNA],
  children: [],
  pending_requests: [],
} as FamilyView

const ANALYSIS: Analysis = {
  steps: [
    { key: 'profile', label: 'Czytam twoje dane', detail: 'Rodzice: 1.', status: 'done' },
    { key: 'family', label: 'Sprawdzam skład rodziny', detail: 'Dzieci: 2, w drodze: 1.', status: 'done' },
    { key: 'match', label: 'Dopasowuję świadczenia', detail: 'Pasuje: 7.', status: 'done' },
  ],
  totals: { national: 20, local: 2, fits: 7, maybe: 5, no: 10 },
  estimated_annual_total: 12000,
  nearest_deadline: null,
  parameters_label: 'Parametry ZUS 2026 – aktywne',
}

function Tree() {
  return (
    <Routes>
      <Route path="/analiza" element={<AnalysisPage />} />
      <Route path="/" element={<p>Panel główny</p>} />
      <Route path="/start" element={<p>Start</p>} />
    </Routes>
  )
}

/** Przewija czas o `ms` i opróżnia mikrozadania (odpowiedzi atrapy API). */
async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

/** Doprowadza analizę do końca: najpierw odpowiedź API, potem kolejne kroki (timer rejestruje się po każdym renderze). */
async function finishAnalysis(steps = 3) {
  await advance(0)
  for (let i = 0; i < steps; i++) await advance(STEP_MS)
}

function stubReducedMotion(reduced: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn((query: string) => ({ matches: reduced && query.includes('reduce'), media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
  )
}

describe('AnalysisPage', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    stubReducedMotion(false)
    routeApi({ 'GET /api/analysis': ANALYSIS })
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('ujawnia kroki po kolei, co ~700 ms; bieżący jest „w toku”, ukończone „gotowe”', async () => {
    renderWithSession(<Tree />, { route: '/analiza', session: makeSession({ family: FAMILY }) })
    await advance(0)

    const steps = () => screen.getAllByRole('listitem')
    expect(steps()).toHaveLength(1)
    expect(steps()[0]).toHaveTextContent('Czytam twoje dane')
    expect(steps()[0]).toHaveTextContent('w toku')
    expect(screen.queryByText('Rodzice: 1.')).not.toBeInTheDocument() // szczegóły dopiero po ukończeniu kroku

    await advance(STEP_MS)
    expect(steps()).toHaveLength(2)
    expect(steps()[0]).toHaveTextContent('gotowe')
    expect(screen.getByText('Rodzice: 1.')).toBeInTheDocument()
    expect(steps()[1]).toHaveTextContent('Sprawdzam skład rodziny')
    expect(steps()[1]).toHaveTextContent('w toku')

    await advance(STEP_MS)
    expect(steps()).toHaveLength(3)
    expect(steps()[2]).toHaveTextContent('w toku')
    expect(screen.queryByRole('button', { name: /przejdź do panelu/i })).not.toBeInTheDocument()

    await advance(STEP_MS) // ostatni krok kończy się — lista ustępuje wynikowi
    expect(screen.getByRole('region', { name: /wynik analizy/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /przejdź do panelu/i })).toBeInTheDocument()
  })

  it('pokazuje na końcu liczby z API', async () => {
    renderWithSession(<Tree />, { route: '/analiza', session: makeSession({ family: FAMILY }) })
    await finishAnalysis()
    const result = screen.getByRole('region', { name: /wynik analizy/i })
    expect(result).toHaveTextContent('12świadczeń i ulg dla Was')
    expect(result).toHaveTextContent('7 pasuje')
    expect(result).toHaveTextContent('5 do sprawdzenia')
  })

  it('wyróżnia pełną nazwę najpilniejszego terminu', async () => {
    routeApi({
      'GET /api/analysis': {
        ...ANALYSIS,
        nearest_deadline: {
          date: '2026-11-25',
          benefit_id: 'pregnancy-certificate',
          benefit_name: 'Zaświadczenie lekarskie o ciąży dla pracodawcy (Dziecko w drodze)',
        },
      },
    })
    renderWithSession(<Tree />, { route: '/analiza', session: makeSession({ family: FAMILY }) })
    await finishAnalysis()

    expect(screen.getByText('Najpilniejsze: Zaświadczenie lekarskie o ciąży dla pracodawcy (Dziecko w drodze)')).toHaveClass(
      'analysis-deadline',
    )
  })

  it('przycisk prowadzi do panelu', async () => {
    renderWithSession(<Tree />, { route: '/analiza', session: makeSession({ family: FAMILY }) })
    await finishAnalysis()
    fireEvent.click(screen.getByRole('button', { name: /przejdź do panelu/i }))
    expect(screen.getByText('Panel główny')).toBeInTheDocument()
  })

  it('prefers-reduced-motion: wszystko od razu, bez odliczania', async () => {
    stubReducedMotion(true)
    renderWithSession(<Tree />, { route: '/analiza', session: makeSession({ family: FAMILY }) })
    await advance(0)
    expect(screen.getByRole('region', { name: /wynik analizy/i })).toHaveTextContent('7 pasuje')
    expect(screen.getByRole('button', { name: /przejdź do panelu/i })).toBeInTheDocument()
  })

  it('bez rodziny przekierowuje na /start', async () => {
    renderWithSession(<Tree />, { route: '/analiza', session: makeSession({ family: null }) })
    await advance(0)
    expect(screen.getByText('Start')).toBeInTheDocument()
  })

  it('błąd API pokazuje komunikat zamiast kroków', async () => {
    const { ApiError } = await import('../../lib/api')
    routeApi({ 'GET /api/analysis': new ApiError(500, 'Coś poszło nie tak.') })
    renderWithSession(<Tree />, { route: '/analiza', session: makeSession({ family: FAMILY }) })
    await advance(0)
    expect(screen.getByRole('alert')).toHaveTextContent('Coś poszło nie tak.')
  })
})
