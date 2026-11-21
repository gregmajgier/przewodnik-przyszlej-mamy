# NOTES-06 — decyzje i odstępstwa (plan 06 czat)

## Rozszerzenia kontraktów / odstępstwa od planu
- **Wersja `mcp`:** zainstalowany SDK to `mcp==2.3.0` (nowe API: `mcp.server.Server` z `on_list_tools/on_call_tool`
  i `mcp.Client`; brak `FastMCP` i `mcp.shared.memory.create_connected_server_and_client_session` z planu).
  `build_mcp_server(ctx_factory) -> Server` używa niskopoziomowego `Server`, żeby przekazać schematy JSON z rejestru
  planu 02 bez zmian.
- **Kontekst narzędzi bez `contextvars`:** `ToolContext` (Principal z tokena, store, data) jest zamknięty w
  `ctx_factory` serwera MCP tworzonego per żądanie (`McpClient(ToolContext(...))`). Efekt ten sam (tożsamość nie
  pochodzi z argumentów modelu), a nie ma ryzyka, że zadanie serwera MCP odziedziczy zły kontekst.
- `McpClient` otwiera krótką sesję na każde `list_tools`/`call` — klient MCP używa task group, której nie wolno
  trzymać otwartej przez `yield` generatora SSE. `call` nie rzuca przy błędzie narzędzia, tylko zwraca tekst
  „Błąd narzędzia …” (trafia do modelu).
- **Streaming:** abstrakcja `LLM` (plan 02) zwraca całą odpowiedź, więc zdarzenia `token` to porcje (wyrazy) już
  gotowej odpowiedzi, nie prawdziwy streaming modelu. Zmiana wymagałaby metody `chat_stream` w `LLM`.
- `run_chat_turn(..., usage: Usage | None = None)` — dodatkowy argument do rozliczenia tokenów (generator nie
  może używać `track_usage()` przez `yield`). Router wywołuje `record_usage`, a gdy nic nie zużyto — `guard.release()`.
- Zdarzenie `done` niesie `session_id`; zdarzenie `tool` ma `{name, ok}` (bez argumentów — mogą zawierać dane).
- `sources` zawiera tylko źródła **faktycznie przywołane** w odpowiedzi (artykuł `art. N` albo link), nie wszystko,
  co znalazły narzędzia. Ten sam numer artykułu w kilku aktach wymaga nazwy aktu w odpowiedzi.
- Sesje czatu należą do **rodzica** (`user_id`), nie do całej rodziny (spec: „historia zapisywana per rodzic”);
  sesja drugiego rodzica z tej samej rodziny wygląda jak nieistniejąca (404).
- Odrzucone żądanie (422/404 sesji) zwraca rezerwację tokenów (`guard.release()`), choć zużywa okno limitu zapytań.
- Dodatkowe endpointy: `GET /api/chat/sessions` (lista własnych sesji).
- Zależności: `httpx==0.28.1` (web search; wcześniej tylko dev) i `mcp==2.3.0` w `requirements.txt`.
  Nowe ustawienia: `WEB_SEARCH_PROVIDER`, `WEB_SEARCH_API_KEY`. `profil_rodziny` zawiera też `situation`/`situation_kind`
  dziecka (potrzebne planowi 10).
- Demo: handler `chat` (`app/seed/demo_chat.py`, import jedną linią w `seed/__init__`) przechodzi przez prawdziwą pętlę —
  w 1. rundzie woła `szukaj_w_przepisach`, w 2. składa odpowiedź z wyniku.
- Frontend: `lib/api.ts` dostało eksport `apiUrl()` (strumień SSE czyta odpowiedź sam). Pływający launcher z planu
  zrealizowano jako kafelek dashboardu (`widget.tsx`, order 5), zgodnie z opisem interfejsu w Task 5.

## Indeks przepisów
- 8 aktów z API Sejmu (PDF tekstu jednolitego, stan na 2026-11-21): Kodeks pracy (tylko dział VIII), ustawa zasiłkowa,
  świadczenia rodzinne, 800+, Prawo oświatowe (art. 130–170, rekrutacja), opieka nad dziećmi do lat 3, „Za życiem”,
  Karta Dużej Rodziny. HTML bywa niedostępny dla najnowszych tekstów, więc skrypt używa PDF (`pypdf`).
- Link w chunku prowadzi do ISAP (`DocDetails.xsp?id=W…`) obwieszczenia o tekście jednolitym; numer artykułu jest w polu `article`.
- Ekstrakcja PDF wstawia spacje przed znakami diakrytycznymi („macierzy ńskiego”) — `repair_diacritics` je naprawia
  (pewne przypadki ą/ę/ń zawsze, niejednoznaczne ć/ł/ó/ś/ź/ż wg słownika prefiksów korpusu). Zostają pojedyncze pozostałości.
- Notki o przepisach przejściowych/uchylonych (<40 znaków, np. „(uchylony)”) są pomijane.
- Dane nie są poradą prawną i nie zastępują weryfikacji w ISAP; ranking BM25 nie rozumie synonimów (np. „tacierzyński”).

## Niezweryfikowane
- Brak prawdziwego wywołania Brave/Serper (testy na `httpx.MockTransport`) i Foundry z narzędziami (tylko `FakeLLM`).
- Zachowanie „pytanie spoza zakresu → uprzejma odmowa” zależy od modelu; testowana jest tylko treść system promptu.
- Czas życia zależności `ai_guard` przy `StreamingResponse` (slot równoległości zwalniany po zakończeniu strumienia)
  sprawdzony tylko pośrednio testami przez `TestClient`.
