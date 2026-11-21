# NOTES-06 — decyzje i odstępstwa (plan 06 czat)

## Indeks przepisów
- Źródło: `api.sejm.gov.pl/eli` (sieć była dostępna). Dla aktualnych obwieszczeń API ma tylko `text.pdf`
  (`textHTML: false`; `text.html` zwraca pustą odpowiedź), więc skrypt czyta PDF przez `pdfplumber`
  (dev-dependency, nie jest potrzebny do działania aplikacji). Wersje HTML istnieją tylko dla wygasłych
  tekstów jednolitych — nie używamy ich (nieaktualne).
- Użyte obwieszczenia (stan na 2026-11-21): KP Dz.U. 2026 poz. 1245 (tylko dział VIII), ustawa zasiłkowa
  2026/854, świadczenia rodzinne 2026/1240, 800+ 2026/508, Prawo oświatowe 2026/820 (rozdz. 2 i 6: wychowanie
  przedszkolne/obowiązek szkolny oraz rekrutacja), żłobki 2025/798, „Za życiem” 2024/1829, KDR 2024/1512.
- Teksty jednolite drukują obok siebie brzmienie obecne i nowe. Skrypt odrzuca: brzmienia, które wejdą
  w życie po dniu budowy („wejdzie w życie z dniem D”), oraz przestarzałe („w tym brzmieniu obowiązuje do
  wejścia w życie zmiany z odnośnika K”, gdy K już obowiązuje). Heurystyka oparta na przypisach — plik
  oznaczony `"verify": true`; wynik sprawdzony ręcznie na próbkach (m.in. KP art. 180, ustawa zasiłkowa art. 29/31/69).
- Znane drobiazgi: oficjalny PDF drukuje kilka wyrazów bez spacji (np. „niewięcej”, „niepóźniej”) — skrypt
  dopisuje spację (`GLUED`), ale nie rekonstruuje brakujących przecinków. Punkty ustępów są sklejone spacją
  w jeden akapit. Artykuły „(uchylony)” są pomijane. Indeksy górne w numerach artykułów zapisane unikodem
  („Art. 180¹”, „Art. 182¹ᵃ”).
- Link w `LawChunk.url` prowadzi do strony obwieszczenia w ISAP (`DocDetails.xsp?id=WDU…`), nie do
  poszczególnego artykułu (ISAP nie ma kotwic dla artykułów z PDF); numer artykułu jest w `article`.
- BM25 własny, `B=0.4`; zapytanie z numerem („art. 180”) mnoży wynik trafionego artykułu ×3.
  Jakość wyszukiwania jest umiarkowana (stemming prefiksowy 5 znaków) — to retrieval dla modelu, nie ostateczna odpowiedź.

## MCP
- Zainstalowany `mcp` to **2.3.0** (`mcp==2.3.0` w requirements.txt): `FastMCP` zniknął (→ `MCPServer`),
  klient to `mcp.Client`, typy w `mcp_types`. Narzędzia z rejestru mają dowolne schematy JSON, więc użyłem
  niskopoziomowego `mcp.server.Server` (`on_list_tools`/`on_call_tool`) zamiast `MCPServer.tool()`
  (który wyprowadza schemat z sygnatury funkcji). `build_mcp_server` zwraca więc `Server`, nie `FastMCP`.
- `McpClient` (transport w pamięci, `mcp.Client(server)`) otwiera połączenie na każde wywołanie — bez zadań
  w tle trzymanych między `yield`-ami strumienia SSE. `ToolContext` przechodzi przez `ContextVar`; brak
  kontekstu = błąd (fail-closed); testy sprawdzają izolację rodzin i równoległych klientów.
- Narzędzia nie przyjmują żadnego identyfikatora rodziny/użytkownika (schemat `additionalProperties: false`).

## Czat
- `LLM` z planu 02 nie ma streamingu — odpowiedź jest generowana w całości, a SSE dzieli ją na porcje
  (`token`). Prawdziwy streaming tokenów wymaga `LLM.stream()` (nie ruszałem planu 02).
- Sesje: `chat_sessions` kluczowane `user_id` (historia per rodzic wg spec §11a; cudza sesja = 404, także DELETE
  i dopisanie wiadomości). Zapis: wiadomość użytkownika od razu, odpowiedź na końcu; przy przerwaniu
  połączenia zapisujemy częściową z `interrupted: true`; nie ma stanu „w trakcie”. „Szyfrowanie” historii
  (spec) = szyfrowanie w spoczynku Cosmos DB; osobnego szyfrowania aplikacyjnego nie dodałem.
- Zdarzenie SSE `session` (pierwsze) dodane ponad listę z planu; `done` bez danych. `sources` zawiera tylko
  źródła faktycznie zacytowane w odpowiedzi (artykuł „Art. N” lub URL), nie wszystkie zwrócone przez narzędzia.
- Rezerwacja budżetu: zużycie tokenów sumowane z `LLMResult.usage` (parametr `usage=` w `run_chat_turn`),
  rozliczane `record_usage`, a przy braku zużycia/odrzuceniu zapytania `ctx.release()`.
- Prompt injection: wynik narzędzia owijany `<wynik_narzedzia nazwa="…">…</wynik_narzedzia>`, znaczniki
  w treści zastępowane; system prompt zakazuje wykonywania poleceń z wyników. To obrona warstwowa, nie gwarancja.
- Demo: handler w `seed/demo_chat.py` (nowy plik, import w `routers/chat.py`, bez edycji `seed/__init__`).
- Zmiany w plikach innych planów (minimalne): `config.py` (`web_search_*`), `.env.example`, `lib/api.ts`
  (eksport `BASE_URL`), `docs/dev.md`.

## Frontend
- Kafelek (`widget.tsx`, order 5) przenosi do `/czat?q=…`; `ChatPage` wysyła pytanie raz i czyści adres.
  Id sesji w `localStorage` (`chat.session`); po odświeżeniu historia jest odtwarzana z API.
- Brak „pływającego” launchera na każdej stronie — tylko kafelek dashboardu i pozycja w nawigacji.

## Niezweryfikowane
- Dostawcy web search (Brave, Serper) testowani wyłącznie atrapą HTTP (`httpx.MockTransport`); kształt
  odpowiedzi z pamięci dokumentacji, bez wywołania prawdziwego API.
- Czat z prawdziwym modelem Foundry nie był uruchamiany (brak poświadczeń); zachowanie tool-calling sprawdzone
  tylko na `FakeLLM`.
- Frontend: brak testu w prawdziwej przeglądarce (tylko vitest/jsdom).
