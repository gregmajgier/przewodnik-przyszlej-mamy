import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Component as JaskolkaPage } from './JaskolkaPage'

const SITUATIONS = [
  { id: 'poronienie', label: 'Poronienie', intro: 'Bardzo ci współczujemy.' },
  { id: 'wczesniak', label: 'Wcześniak lub dziecko w szpitalu', intro: 'To wyczerpujący czas.' },
]

const DETAIL = {
  ...SITUATIONS[0],
  checklist: [
    {
      id: 'skrocony-urlop',
      title: 'Skrócony urlop macierzyński',
      body: 'Przysługuje ci 8 tygodni.',
      kind: 'right',
      deadline_text: 'W ciągu 12 miesięcy',
      form_codes: ['Z-12'],
      source_url: 'https://www.gov.pl/test',
      verify: true,
    },
    {
      id: 'zaswiadczenie',
      title: 'Zaświadczenie lekarskie',
      body: 'Poproś w szpitalu.',
      kind: 'document',
      deadline_text: null,
      form_codes: [],
      source_url: 'https://www.zus.pl/test',
      verify: false,
    },
  ],
}

const FOUNDATIONS = [
  { id: 'a', name: 'Fundacja Ogólnopolska', description: 'Pomaga.', url: 'https://a.example', situations: ['poronienie'], region: null },
  { id: 'b', name: 'Hospicjum Lubelskie', description: 'Wspiera.', url: 'https://b.example', situations: ['poronienie'], region: 'Lublin' },
  { id: 'c', name: 'Hospicjum Gdańskie', description: 'Wspiera.', url: 'https://c.example', situations: ['poronienie'], region: 'Pomorze' },
]

let fetchMock: ReturnType<typeof vi.fn>
let foundations = FOUNDATIONS

function respond(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }))
}

beforeEach(() => {
  foundations = FOUNDATIONS
  fetchMock = vi.fn((url: string) => {
    if (url.endsWith('/api/jaskolka/situations')) return respond(SITUATIONS)
    if (url.endsWith('/api/jaskolka/situations/poronienie')) return respond(DETAIL)
    if (url.includes('/api/jaskolka/situations/')) return respond({ detail: 'Nie ma takiej sytuacji.' }, 404)
    if (url.includes('/api/jaskolka/foundations')) return respond(foundations)
    return respond({ detail: 'brak' }, 404)
  })
  vi.stubGlobal('fetch', fetchMock)
  sessionStorage.clear()
  delete document.documentElement.dataset.theme
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function renderAt(route: string) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/jaskolka" element={<JaskolkaPage />} />
        <Route path="/jaskolka/:situationId" element={<JaskolkaPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('/jaskolka bez logowania', () => {
  it('nie wywołuje /api/me i nie wysyła nagłówka Authorization, nawet gdy w przeglądarce jest token', async () => {
    localStorage.setItem('token', 'sekretny-token')
    renderAt('/jaskolka/poronienie')
    await screen.findByText('Skrócony urlop macierzyński')
    await screen.findByText('Fundacja Ogólnopolska')

    expect(fetchMock).toHaveBeenCalled()
    for (const [url, init] of fetchMock.mock.calls as [string, RequestInit | undefined][]) {
      expect(url).not.toContain('/api/me')
      expect(url).toContain('/api/jaskolka/')
      expect(new Headers(init?.headers).has('Authorization')).toBe(false)
      expect(init?.credentials).toBe('omit')
    }
  })

  it('pokazuje wybór sytuacji i po kliknięciu ładuje checklistę', async () => {
    renderAt('/jaskolka')
    const link = await screen.findByRole('link', { name: 'Poronienie' })
    expect(screen.getByRole('link', { name: /Wcześniak/ })).toBeInTheDocument()
    await userEvent.click(link)
    expect(await screen.findByRole('heading', { level: 1, name: 'Poronienie' })).toBeInTheDocument()
    expect(screen.getByText('Skrócony urlop macierzyński')).toBeInTheDocument()
    expect(screen.getByText('W ciągu 12 miesięcy')).toBeInTheDocument()
    expect(screen.getByText(/Z-12/)).toBeInTheDocument()
    expect(screen.getByText(/może wymagać potwierdzenia/)).toBeInTheDocument()
  })

  it('odhaczenie zapisuje się w sessionStorage i wraca po ponownym wejściu', async () => {
    const { unmount } = renderAt('/jaskolka/poronienie')
    const box = await screen.findByRole('checkbox', { name: /Skrócony urlop macierzyński/ })
    expect(box).not.toBeChecked()
    await userEvent.click(box)
    expect(box).toBeChecked()
    expect(JSON.parse(sessionStorage.getItem('jaskolka:checked:poronienie') ?? '[]')).toEqual(['skrocony-urlop'])
    expect(localStorage.length).toBe(0)
    unmount()

    renderAt('/jaskolka/poronienie')
    expect(await screen.findByRole('checkbox', { name: /Skrócony urlop macierzyński/ })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: /Zaświadczenie lekarskie/ })).not.toBeChecked()
  })

  it('ustawia motyw mono na czas wizyty i przywraca poprzedni po wyjściu', async () => {
    document.documentElement.dataset.theme = 'standard'
    const { unmount } = renderAt('/jaskolka')
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('mono'))
    unmount()
    expect(document.documentElement.dataset.theme).toBe('standard')
  })

  it('usuwa atrybut motywu, jeśli wcześniej go nie było', async () => {
    const { unmount } = renderAt('/jaskolka')
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('mono'))
    unmount()
    expect(document.documentElement.dataset.theme).toBeUndefined()
  })

  it('zawsze pokazuje link „Wróć” oraz telefon wsparcia', async () => {
    renderAt('/jaskolka')
    await screen.findByRole('link', { name: 'Poronienie' })
    expect(screen.getByRole('link', { name: /Wróć do mRodziny/ })).toHaveAttribute('href', '/')
    const phone = screen.getByRole('link', { name: /116 123/ })
    expect(phone).toHaveAttribute('href', 'tel:116123')
    expect(screen.getByText(/Potrzebujesz porozmawiać/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('link', { name: 'Poronienie' }))
    await screen.findByText('Skrócony urlop macierzyński')
    expect(screen.getByRole('link', { name: /Wróć do wyboru sytuacji/ })).toHaveAttribute('href', '/jaskolka')
    expect(screen.getByRole('link', { name: /116 123/ })).toBeInTheDocument()
  })

  it('nieznana sytuacja pokazuje komunikat po polsku i link do listy, nie biały ekran', async () => {
    renderAt('/jaskolka/nie-ma')
    expect(await screen.findByRole('alert')).toHaveTextContent('Nie ma takiej sytuacji.')
    expect(screen.getByRole('link', { name: /Wybierz sytuację/ })).toHaveAttribute('href', '/jaskolka')
  })

  it('filtr regionu zawęża fundacje, ogólnopolskie zostają; pusty wynik daje komunikat', async () => {
    renderAt('/jaskolka/poronienie')
    await screen.findByText('Hospicjum Gdańskie')
    await userEvent.selectOptions(screen.getByLabelText('Gdzie mieszkasz'), 'Lublin')
    expect(screen.queryByText('Hospicjum Gdańskie')).not.toBeInTheDocument()
    expect(screen.getByText('Hospicjum Lubelskie')).toBeInTheDocument()
    expect(screen.getByText('Fundacja Ogólnopolska')).toBeInTheDocument()
  })

  it('pusta lista fundacji pokazuje komunikat z telefonem wsparcia', async () => {
    foundations = []
    renderAt('/jaskolka/poronienie')
    const status = await screen.findByText(/Nie mamy jeszcze organizacji/)
    expect(status).toHaveTextContent('116 123')
    expect(within(screen.getByRole('main')).queryAllByRole('listitem')).toHaveLength(2) // tylko checklista
  })
})

describe('marka: tylko tokeny motywu', () => {
  const dir = __dirname
  const files = readdirSync(dir).filter((f) => /\.(tsx?|css)$/.test(f) && !/\.test\./.test(f))

  it('w komponentach i arkuszu /jaskolka nie ma wpisanych kolorów hex', () => {
    expect(files).toContain('jaskolka.css')
    for (const f of files) {
      const src = readFileSync(join(dir, f), 'utf8')
      expect(src, `${f} zawiera kolor hex`).not.toMatch(/#[0-9a-fA-F]{3,8}\b/)
    }
  })

  it('arkusz używa tokenów motywu i kształtów marki', () => {
    const css = readFileSync(join(dir, 'jaskolka.css'), 'utf8')
    for (const token of ['var(--bg)', 'var(--fg)', 'var(--primary)', 'var(--surface)', 'var(--border)']) {
      expect(css).toContain(token)
    }
    expect(css).toMatch(/border-radius:\s*999px/)
    expect(css).toMatch(/border-radius:\s*1\.5rem/)
    expect(css).toMatch(/font-weight:\s*800/)
    expect(css).toContain('0 6px 24px rgb(25 25 25 / 0.08)')
    expect(css).toContain('prefers-reduced-motion')
  })
})
