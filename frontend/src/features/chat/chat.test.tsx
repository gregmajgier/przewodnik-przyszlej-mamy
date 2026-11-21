import { act, render, renderHook, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../lib/api'
import { SessionContext } from '../../lib/session'
import { makeSession, renderWithSession } from '../../test/utils'
import ChatLauncher from './ChatLauncher'
import ChatPage from './ChatPage'
import { useChatStream } from './useChatStream'

vi.mock('../../lib/api', async (orig) => ({
  ...(await orig<typeof import('../../lib/api')>()),
  api: vi.fn(),
}))

const enc = new TextEncoder()

function sse(name: string, data: unknown): string {
  return `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`
}

/** Odpowiedź SSE podzielona na dowolne kawałki (też w środku zdarzenia). */
function sseResponse(chunks: string[], init: ResponseInit = { status: 200 }): Response {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const c of chunks) controller.enqueue(enc.encode(c))
      controller.close()
    },
  })
  return new Response(stream, { headers: { 'Content-Type': 'text/event-stream' }, ...init })
}

const SOURCE = {
  kind: 'przepis',
  article: 'Art. 180',
  title: 'Art. 180 — Kodeks pracy',
  url: 'https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU20260001245',
}

function happyStream(): string[] {
  const all =
    sse('session', { session_id: 's1' }) +
    sse('tool', { name: 'szukaj_w_przepisach' }) +
    sse('token', { text: 'Urlop macierzyński ' }) +
    sse('token', { text: 'trwa 20 tygodni ' }) +
    sse('token', { text: '(Art. 180 KP).' }) +
    sse('sources', { sources: [SOURCE] }) +
    sse('done', {})
  // tnie w losowym miejscu — parser musi składać zdarzenia z kawałków
  return [all.slice(0, 37), all.slice(37, 150), all.slice(150)]
}

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  vi.mocked(api).mockReset()
  vi.mocked(api).mockImplementation((async (path: string) => {
    if (path === '/api/ai/status') return { mode: 'live', available: true }
    throw new Error(`nieoczekiwane api ${path}`)
  }) as unknown as typeof api)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useChatStream', () => {
  it('składa strumień tokenów w jedną wiadomość i zapamiętuje sesję', async () => {
    fetchMock.mockResolvedValueOnce(sseResponse(happyStream()))
    const { result } = renderHook(() => useChatStream())
    await act(async () => {
      await result.current.send('Jak działa urlop macierzyński?')
    })
    const msgs = result.current.messages
    expect(msgs.map((m) => m.role)).toEqual(['user', 'assistant'])
    expect(msgs[0].text).toBe('Jak działa urlop macierzyński?')
    expect(msgs[1].text).toBe('Urlop macierzyński trwa 20 tygodni (Art. 180 KP).')
    expect(msgs[1].sources).toEqual([SOURCE])
    expect(result.current.sending).toBe(false)
    expect(result.current.sessionId).toBe('s1')
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/api/chat')
    expect(JSON.parse(init.body)).toEqual({ session_id: null, message: 'Jak działa urlop macierzyński?' })
  })

  it('druga wiadomość dołącza do tej samej sesji', async () => {
    fetchMock
      .mockResolvedValueOnce(sseResponse(happyStream()))
      .mockResolvedValueOnce(sseResponse([sse('session', { session_id: 's1' }), sse('token', { text: 'ok' }), sse('done', {})]))
    const { result } = renderHook(() => useChatStream())
    await act(async () => result.current.send('pierwsze'))
    await act(async () => result.current.send('drugie'))
    expect(JSON.parse(fetchMock.mock.calls[1][1].body).session_id).toBe('s1')
    expect(result.current.messages).toHaveLength(4)
  })

  it('429 pokazuje spokojny komunikat z API i nie zostawia pustej odpowiedzi', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Zbyt wiele zapytań do asystenta. Spróbuj za chwilę.' }), {
        status: 429,
        headers: { 'Content-Type': 'application/json', 'Retry-After': '30' },
      }),
    )
    const { result } = renderHook(() => useChatStream())
    await act(async () => result.current.send('pytanie'))
    expect(result.current.notice).toBe('Zbyt wiele zapytań do asystenta. Spróbuj za chwilę.')
    expect(result.current.messages.map((m) => m.role)).toEqual(['user'])
    expect(result.current.sending).toBe(false)
  })

  it('zdarzenie error z serwera trafia do komunikatu', async () => {
    fetchMock.mockResolvedValueOnce(
      sseResponse([sse('session', { session_id: 's9' }), sse('error', { message: 'Asystent AI jest chwilowo niedostępny.' })]),
    )
    const { result } = renderHook(() => useChatStream())
    await act(async () => result.current.send('pytanie'))
    expect(result.current.notice).toBe('Asystent AI jest chwilowo niedostępny.')
    expect(result.current.messages.at(-1)?.role).toBe('user')
  })

  it('błąd sieci daje czytelny komunikat', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('fail'))
    const { result } = renderHook(() => useChatStream())
    await act(async () => result.current.send('pytanie'))
    expect(result.current.notice).toMatch(/połączenia/i)
  })

  it('reset czyści rozmowę i sesję', async () => {
    fetchMock.mockResolvedValueOnce(sseResponse(happyStream()))
    const { result } = renderHook(() => useChatStream())
    await act(async () => result.current.send('pytanie'))
    act(() => result.current.reset())
    expect(result.current.messages).toEqual([])
    expect(result.current.sessionId).toBeNull()
    expect(result.current.notice).toBeNull()
  })
})

describe('ChatPage', () => {
  it('renderuje odpowiedź ze źródłami jako linkami', async () => {
    fetchMock.mockResolvedValueOnce(sseResponse(happyStream()))
    renderWithSession(<ChatPage />, { route: '/czat' })
    await userEvent.type(screen.getByLabelText('Twoje pytanie'), 'Jak działa urlop macierzyński?')
    await userEvent.click(screen.getByRole('button', { name: 'Wyślij' }))
    expect(await screen.findByText(/Urlop macierzyński trwa 20 tygodni/)).toBeInTheDocument()
    const link = await screen.findByRole('link', { name: /Art\. 180 — Kodeks pracy/ })
    expect(link).toHaveAttribute('href', SOURCE.url)
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'))
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('429 pokazuje komunikat w spokojnym banerze (nie alarmie)', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Asystent AI jest dziś przeciążony. Spróbuj jutro.' }), {
        status: 429,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    renderWithSession(<ChatPage />, { route: '/czat' })
    await userEvent.type(screen.getByLabelText('Twoje pytanie'), 'pytanie')
    await userEvent.click(screen.getByRole('button', { name: 'Wyślij' }))
    const banner = await screen.findByRole('status', { name: /komunikat/i })
    expect(banner).toHaveTextContent('Asystent AI jest dziś przeciążony. Spróbuj jutro.')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('„Nowa rozmowa” czyści okno i wraca do przykładów', async () => {
    fetchMock.mockResolvedValueOnce(sseResponse(happyStream()))
    renderWithSession(<ChatPage />, { route: '/czat' })
    await userEvent.type(screen.getByLabelText('Twoje pytanie'), 'pytanie')
    await userEvent.click(screen.getByRole('button', { name: 'Wyślij' }))
    await screen.findByText(/Urlop macierzyński trwa/)
    await userEvent.click(screen.getByRole('button', { name: 'Nowa rozmowa' }))
    expect(screen.queryByText(/Urlop macierzyński trwa/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Jak działa urlop macierzyński?' })).toBeInTheDocument()
  })

  it('przykładowe pytanie wysyła się jednym kliknięciem', async () => {
    fetchMock.mockResolvedValueOnce(sseResponse(happyStream()))
    renderWithSession(<ChatPage />, { route: '/czat' })
    await userEvent.click(screen.getByRole('button', { name: 'Jak zapisać dziecko do przedszkola?' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).message).toBe('Jak zapisać dziecko do przedszkola?')
  })

  it('test_url_q_param_is_not_sent_automatically', async () => {
    renderWithSession(<ChatPage />, { route: '/czat?q=Co%20mi%20przys%C5%82uguje%3F' })
    await screen.findByLabelText('Twoje pytanie')
    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.getByLabelText('Twoje pytanie')).toHaveValue('')
  })

  it('test_launcher_question_prefills_draft_without_sending', async () => {
    render(
      <SessionContext.Provider value={makeSession()}>
        <MemoryRouter initialEntries={[{ pathname: '/czat', state: { q: 'Co mi przysługuje?' } }]}>
          <ChatPage />
        </MemoryRouter>
      </SessionContext.Provider>,
    )
    expect(screen.getByLabelText('Twoje pytanie')).toHaveValue('Co mi przysługuje?')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('pokazuje etykietę trybu demo', async () => {
    vi.mocked(api).mockImplementation((async () => ({ mode: 'demo', available: true })) as unknown as typeof api)
    renderWithSession(<ChatPage />, { route: '/czat' })
    expect(await screen.findByText(/tryb demo/i)).toBeInTheDocument()
  })

  it('Enter wysyła, Shift+Enter dodaje nową linię; pusta wiadomość nie jest wysyłana', async () => {
    fetchMock.mockResolvedValueOnce(sseResponse(happyStream()))
    renderWithSession(<ChatPage />, { route: '/czat' })
    expect(screen.getByRole('button', { name: 'Wyślij' })).toBeDisabled()
    const box = screen.getByLabelText('Twoje pytanie')
    await userEvent.type(box, 'a{Shift>}{Enter}{/Shift}b')
    expect(box).toHaveValue('a\nb')
    await userEvent.type(box, '{Enter}')
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
  })
})

describe('ChatLauncher', () => {
  it('pokazuje pole i przykłady, a wysłanie przenosi do /czat bez wysyłania pytania', async () => {
    renderWithSession(
      <Routes>
        <Route path="/" element={<ChatLauncher />} />
        <Route path="/czat" element={<ChatPage />} />
      </Routes>,
      { session: makeSession() },
    )
    expect(screen.getByRole('heading', { name: 'Zapytaj mRodzinę' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Jak zapisać dziecko do przedszkola?' })).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Zadaj pytanie'), 'Co mi przysługuje po urlopie?')
    await userEvent.click(screen.getByRole('button', { name: 'Zapytaj' }))
    expect(await screen.findByLabelText('Twoje pytanie')).toHaveValue('Co mi przysługuje po urlopie?')
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
