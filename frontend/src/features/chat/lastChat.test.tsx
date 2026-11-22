import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setToken } from '../../lib/api'
import { SessionContext } from '../../lib/session'
import { ANNA, makeSession, renderWithSession } from '../../test/utils'
import { AskFab } from './AskFab'
import ChatPage from './ChatPage'
import { clearLastChat, getLastChat, setLastChat } from './lastChat'

const enc = new TextEncoder()
const sse = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`

function streamResponse(chunks: string[]): Response {
  const stream = new ReadableStream<Uint8Array>({
    start(c) {
      for (const x of chunks) c.enqueue(enc.encode(x))
      c.close()
    },
  })
  return new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  setToken('tok-123')
  clearLastChat(ANNA.id)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function Where() {
  const loc = useLocation()
  const state = (loc.state ?? {}) as { resume?: string }
  return <p data-testid="where">{`${loc.pathname}|${state.resume ?? ''}`}</p>
}

describe('ostatnia rozmowa z asystentem', () => {
  it('po odpowiedzi czatu zapamiętuje id rozmowy (tylko id, bez treści)', async () => {
    fetchMock.mockResolvedValueOnce(
      streamResponse([sse('token', { text: 'Odpowiedź.' }), sse('done', { tool_calls: 0, session_id: 'sess-9' })]),
    )
    renderWithSession(
      <Routes>
        <Route path="/czat" element={<ChatPage />} />
      </Routes>,
      { route: '/czat' },
    )
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Twoje pytanie'), 'Jak długo trwa urlop?')
    await user.click(screen.getByRole('button', { name: 'Wyślij' }))
    await waitFor(() => expect(getLastChat(ANNA.id)).toBe('sess-9'))
    expect(localStorage.getItem(`mrodzina:last-chat:${ANNA.id}`)).toBe('sess-9')
  })

  it('karta nad „Zapytaj” pokazuje ostatnią rozmowę i wraca do niej', async () => {
    setLastChat(ANNA.id, 'sess-9')
    fetchMock.mockResolvedValueOnce(json([{ id: 'sess-9', updated_at: '2026-11-22T10:00:00Z', preview: 'Jak długo trwa urlop?' }]))
    renderWithSession(
      <Routes>
        <Route path="/swiadczenia" element={<AskFab />} />
        <Route path="/czat" element={<Where />} />
      </Routes>,
      { route: '/swiadczenia' },
    )
    const card = await screen.findByRole('link', { name: /Ostatnia rozmowa.*Jak długo trwa urlop/ })
    await userEvent.setup().click(card)
    expect(screen.getByTestId('where')).toHaveTextContent('/czat|sess-9')
  })

  it('bez zapamiętanej rozmowy jest tylko przycisk „Zapytaj”', () => {
    renderWithSession(<AskFab />)
    expect(screen.getByRole('link', { name: 'Zapytaj mRodzinę' })).toBeInTheDocument()
    expect(screen.queryByText('Ostatnia rozmowa')).not.toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('kartę można ukryć', async () => {
    setLastChat(ANNA.id, 'sess-9')
    fetchMock.mockResolvedValueOnce(json([{ id: 'sess-9', updated_at: '2026-11-22T10:00:00Z', preview: 'Pytanie' }]))
    renderWithSession(<AskFab />)
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Ukryj ostatnią rozmowę' }))
    expect(screen.queryByText('Ostatnia rozmowa')).not.toBeInTheDocument()
    expect(getLastChat(ANNA.id)).toBeNull()
  })

  it('usuniętej rozmowy (nie ma jej na liście) już nie proponuje', async () => {
    setLastChat(ANNA.id, 'sess-old')
    fetchMock.mockResolvedValueOnce(json([]))
    renderWithSession(<AskFab />)
    await waitFor(() => expect(getLastChat(ANNA.id)).toBeNull())
    expect(screen.queryByText('Ostatnia rozmowa')).not.toBeInTheDocument()
  })

  it('czat otwarty z karty wczytuje zapisaną rozmowę', async () => {
    fetchMock.mockResolvedValueOnce(
      json({
        id: 'sess-9',
        messages: [
          { role: 'user', content: 'Jak długo trwa urlop?' },
          { role: 'assistant', content: 'Urlop macierzyński trwa 20 tygodni.', sources: [] },
        ],
      }),
    )
    render(
      <SessionContext.Provider value={makeSession()}>
        <MemoryRouter initialEntries={[{ pathname: '/czat', state: { resume: 'sess-9', from: '/' } }]}>
          <Routes>
            <Route path="/czat" element={<ChatPage />} />
          </Routes>
        </MemoryRouter>
      </SessionContext.Provider>,
    )
    expect(await screen.findByText('Urlop macierzyński trwa 20 tygodni.')).toBeInTheDocument()
    expect(screen.getByText('Jak długo trwa urlop?')).toBeInTheDocument()
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/chat/sessions/sess-9')
  })

  it('gdy zapisanej rozmowy nie da się wczytać, czat zapomina o niej', async () => {
    setLastChat(ANNA.id, 'sess-gone')
    fetchMock.mockResolvedValueOnce(json({ detail: 'Nie znaleziono rozmowy.' }, 404))
    render(
      <SessionContext.Provider value={makeSession()}>
        <MemoryRouter initialEntries={[{ pathname: '/czat', state: { resume: 'sess-gone' } }]}>
          <Routes>
            <Route path="/czat" element={<ChatPage />} />
          </Routes>
        </MemoryRouter>
      </SessionContext.Provider>,
    )
    expect(await screen.findByText('Nie udało się wczytać rozmowy.')).toBeInTheDocument()
    expect(getLastChat(ANNA.id)).toBeNull()
  })
})
