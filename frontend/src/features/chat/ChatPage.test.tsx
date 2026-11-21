import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setToken } from '../../lib/api'
import { ChatLauncher } from './ChatLauncher'
import ChatPage from './ChatPage'
import { parseSse } from './useChatStream'
import navItem from './nav'
import widget from './widget'

const enc = new TextEncoder()

function sse(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`
}

/** Odpowiedź SSE podzielona na zadane kawałki bajtów (zdarzenia mogą przychodzić w pół zdania). */
function streamResponse(chunks: string[], init: ResponseInit = { status: 200 }): Response {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const c of chunks) controller.enqueue(enc.encode(c))
      controller.close()
    },
  })
  return new Response(stream, { ...init, headers: { 'Content-Type': 'text/event-stream' } })
}

const ANSWER_EVENTS = [
  sse('tool', { name: 'szukaj_w_przepisach', ok: true }),
  sse('token', { text: 'Urlop macierzyński ' }),
  sse('token', { text: 'trwa 20 tygodni ' }),
  sse('token', { text: '(Kodeks pracy, art. 180).' }),
  sse('sources', {
    sources: [{ kind: 'law', title: 'Kodeks pracy, Art. 180', url: 'https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU20260001245' }],
  }),
  sse('done', { tool_calls: 1, session_id: 'sess-1' }),
]

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  setToken('tok-123')
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function renderChat(route = '/czat') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/czat" element={<ChatPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

async function ask(text: string) {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Twoje pytanie'), text)
  await user.click(screen.getByRole('button', { name: 'Wyślij' }))
  return user
}

describe('parseSse', () => {
  it('składa zdarzenia i zostawia niepełny ogon', () => {
    const first = parseSse('event: token\ndata: {"text":"a"}\n\nevent: tok')
    expect(first.events).toEqual([{ event: 'token', data: { text: 'a' } }])
    const second = parseSse(first.rest + 'en\ndata: {"text":"b"}\n\n')
    expect(second.events).toEqual([{ event: 'token', data: { text: 'b' } }])
    expect(second.rest).toBe('')
  })

  it('pomija uszkodzone zdarzenia i obsługuje CRLF', () => {
    const { events } = parseSse('event: token\r\ndata: {zepsute\r\n\r\nevent: done\r\ndata: {"ok":true}\r\n\r\n')
    expect(events).toEqual([{ event: 'done', data: { ok: true } }])
  })
})

describe('ChatPage', () => {
  it('strumień tokenów składa się w jedną wiadomość (także gdy zdarzenia przychodzą w kawałkach)', async () => {
    const joined = ANSWER_EVENTS.join('')
    const cut = joined.indexOf('trwa') + 3 // środek zdarzenia
    fetchMock.mockResolvedValue(streamResponse([joined.slice(0, cut), joined.slice(cut)]))
    renderChat()
    await ask('Jak działa urlop macierzyński?')

    const answers = await screen.findAllByRole('article', { name: 'Odpowiedź mRodziny' })
    expect(answers).toHaveLength(1)
    await waitFor(() => expect(answers[0]).toHaveTextContent('Urlop macierzyński trwa 20 tygodni (Kodeks pracy, art. 180).'))
    expect(screen.getByRole('article', { name: 'Twoja wiadomość' })).toHaveTextContent('Jak działa urlop macierzyński?')

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/chat')
    expect(init.method).toBe('POST')
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok-123')
    expect(JSON.parse(init.body as string)).toEqual({ session_id: null, message: 'Jak działa urlop macierzyński?' })
  })

  it('źródła są linkami, a kolejna wiadomość dostaje id sesji', async () => {
    fetchMock.mockResolvedValueOnce(streamResponse(ANSWER_EVENTS))
    renderChat()
    const user = await ask('urlop?')
    const link = await screen.findByRole('link', { name: /Kodeks pracy, Art\. 180/ })
    expect(link).toHaveAttribute('href', expect.stringContaining('https://isap.sejm.gov.pl/'))
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'))

    fetchMock.mockResolvedValueOnce(streamResponse([sse('token', { text: 'Tak.' }), sse('done', { session_id: 'sess-1' })]))
    await user.type(screen.getByLabelText('Twoje pytanie'), 'A tata?')
    await user.click(screen.getByRole('button', { name: 'Wyślij' }))
    await screen.findByText('Tak.')
    expect(JSON.parse((fetchMock.mock.calls[1][1] as RequestInit).body as string).session_id).toBe('sess-1')
  })

  it('linki i pogrubienia w treści odpowiedzi są renderowane bez HTML', async () => {
    fetchMock.mockResolvedValue(
      streamResponse([
        sse('token', { text: '**Kodeks pracy, Art. 180** — zobacz https://www.zus.pl/a. <b>nie html</b>' }),
        sse('done', { session_id: 's' }),
      ]),
    )
    renderChat()
    await ask('x')
    const article = await screen.findByRole('article', { name: 'Odpowiedź mRodziny' })
    await waitFor(() => expect(within(article).getByText('Kodeks pracy, Art. 180').tagName).toBe('STRONG'))
    expect(within(article).getByRole('link', { name: 'https://www.zus.pl/a' })).toHaveAttribute('href', 'https://www.zus.pl/a')
    expect(article.querySelector('b')).toBeNull()
    expect(article).toHaveTextContent('<b>nie html</b>')
  })

  it('429 pokazuje spokojny komunikat zamiast błędu', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Zbyt wiele zapytań do asystenta. Spróbuj za chwilę.' }), {
        status: 429,
        headers: { 'Content-Type': 'application/json', 'Retry-After': '30' },
      }),
    )
    renderChat()
    await ask('pytanie')
    const banner = await screen.findByRole('status', { name: '' })
    expect(banner).toHaveTextContent('Zbyt wiele zapytań do asystenta. Spróbuj za chwilę.')
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.queryByRole('article', { name: 'Odpowiedź mRodziny' })).toBeNull() // bez pustej bańki
  })

  it('inny błąd HTTP i zdarzenie error pokazują komunikat', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Wiadomość jest za długa (maksymalnie 2000 znaków).' }), { status: 422 }),
    )
    renderChat()
    const user = await ask('x')
    expect(await screen.findByRole('alert')).toHaveTextContent('za długa')

    fetchMock.mockResolvedValueOnce(streamResponse([sse('error', { message: 'Asystent AI jest chwilowo niedostępny.' })]))
    await user.type(screen.getByLabelText('Twoje pytanie'), 'jeszcze raz')
    await user.click(screen.getByRole('button', { name: 'Wyślij' }))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('chwilowo niedostępny'))
  })

  it('brak sieci pokazuje komunikat po polsku', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    renderChat()
    await ask('x')
    expect(await screen.findByRole('alert')).toHaveTextContent('Brak połączenia z serwerem')
  })

  it('przycisk „Nowa rozmowa” czyści wiadomości i zaczyna nową sesję', async () => {
    fetchMock.mockResolvedValueOnce(streamResponse(ANSWER_EVENTS))
    renderChat()
    const user = await ask('urlop?')
    await screen.findByRole('link', { name: /Kodeks pracy/ })
    await user.click(screen.getByRole('button', { name: 'Nowa rozmowa' }))
    expect(screen.queryByRole('article')).toBeNull()
    expect(screen.getByText(/Zapytaj o urlop/)).toBeInTheDocument()

    fetchMock.mockResolvedValueOnce(streamResponse([sse('token', { text: 'ok' }), sse('done', { session_id: 'sess-2' })]))
    await user.type(screen.getByLabelText('Twoje pytanie'), 'nowe');
    await user.click(screen.getByRole('button', { name: 'Wyślij' }))
    await screen.findByText('ok')
    expect(JSON.parse((fetchMock.mock.calls[1][1] as RequestInit).body as string).session_id).toBeNull()
  })

  it('przykładowe pytanie wysyła się jednym kliknięciem', async () => {
    fetchMock.mockResolvedValue(streamResponse([sse('token', { text: 'odp' }), sse('done', { session_id: 's' })]))
    renderChat()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Jak zapisać dziecko do przedszkola?' }))
    await screen.findByText('odp')
    expect(JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string).message).toBe('Jak zapisać dziecko do przedszkola?')
  })

  it('pole ma limit 2000 znaków, a pusta wiadomość nie jest wysyłana', async () => {
    renderChat()
    expect(screen.getByLabelText('Twoje pytanie')).toHaveAttribute('maxlength', '2000')
    expect(screen.getByRole('button', { name: 'Wyślij' })).toBeDisabled()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('pytanie z adresu ?q= nigdy nie jest wysyłane automatycznie ani wpisywane', async () => {
    renderChat('/czat?q=Jak%20dzia%C5%82a%20urlop')
    expect(screen.getByLabelText('Twoje pytanie')).toHaveValue('')
    await new Promise((r) => setTimeout(r, 20))
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('pytanie przekazane w router state trafia tylko do pola i czeka na wysłanie', async () => {
    render(
      <MemoryRouter initialEntries={[{ pathname: '/czat', state: { q: 'Ile trwa urlop?' } }]}>
        <ChatPage />
      </MemoryRouter>,
    )
    expect(screen.getByLabelText('Twoje pytanie')).toHaveValue('Ile trwa urlop?')
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe('kafelek dashboardu', () => {
  function Where() {
    const loc = useLocation()
    return <p data-testid="where">{loc.pathname + ((loc.state as { q?: string } | null)?.q ? `|${(loc.state as { q: string }).q}` : '')}</p>
  }

  function renderLauncher() {
    return render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<ChatLauncher />} />
          <Route path="/czat" element={<Where />} />
        </Routes>
      </MemoryRouter>,
    )
  }

  it('pokazuje przykłady i przenosi pytanie do czatu', async () => {
    renderLauncher()
    expect(screen.getByRole('heading', { name: 'Zapytaj mRodzinę' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Jak działa urlop macierzyński?' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Jak zapisać dziecko do przedszkola?' })).toBeInTheDocument()
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Twoje pytanie'), 'Ile trwa urlop?')
    await user.click(screen.getByRole('button', { name: 'Zapytaj' }))
    expect(screen.getByTestId('where')).toHaveTextContent('/czat|Ile trwa urlop?')
  })

  it('przykład działa jednym kliknięciem', async () => {
    renderLauncher()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Jak działa urlop macierzyński?' }))
    expect(screen.getByTestId('where')).toHaveTextContent('/czat|Jak działa urlop macierzyński?')
  })

  it('jest zarejestrowany jako widget (order 5) i pozycja nawigacji', () => {
    expect(widget.order).toBe(5)
    expect(widget.Component).toBe(ChatLauncher)
    expect(navItem).toMatchObject({ path: '/czat', area: 'parent' })
  })
})
