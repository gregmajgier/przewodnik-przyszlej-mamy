# NOTES-04 — decyzje i odstępstwa (plan 04 skan umów i ryzyka)

## Zmiany w plikach innych planów (minimalne)
- `backend/app/ai/llm.py` (plan 02): `LLMMessage.images: list[str]` (data URL-e) + konwersja do części
  `image_url` w `_to_openai_messages` (FoundryLLM). Wymagane przez „obraz jako część wiadomości”.
- `backend/requirements.txt`: `python-multipart` (FastAPI nie przyjmie uploadu bez niego); `requirements-dev.txt`: `fpdf2`.
- Frontend: brak edycji plików planu 01. Rozszerzenia przez `features/contracts/{routes,nav,widget,profile-section}`;
  `profile-section.tsx` zastępuje placeholder „Umowy o pracę” w „Moich danych”.

## Decyzje
- **Pliku nie przechowujemy** (ani oryginału, ani kopii): po ekstrakcji zostaje szkic z danymi. Dlatego „plik źródłowy
  tylko właściciel” jest spełnione trywialnie; partner widzi zatwierdzone dane, ale `filename` jest dla niego `null`.
  Szyfrowanie pól (spec §14) nie jest tu wdrożone — to temat wspólny, niezależny od planu 04.
- Endpoint `scan` czyta multipart ręcznie (`request.form`), bo parser Starlette nie ma limitu rozmiaru pliku:
  najpierw `Content-Length` (wymagany; brak = 411, > 5 MB + 64 KB = 413), potem twardy limit przy odczycie (413).
  Typ: magic bytes decydują; niezgodność z deklarowanym `Content-Type` albo nieznany typ = 415
  (`application/octet-stream` i pusty = ufamy sniffingowi). Nieczytelny plik/nie-umowa/PDF z JS/zaszyfrowany = 422.
- „Nie umowa”: model zwrócił < 2 z pól (rodzaj, pracodawca, data startu, wynagrodzenie, etat) -> 422, nic nie zapisujemy.
- `ContractDraft` jest łagodny: `fte` poza (0,1] i `gross_monthly` <= 0 zamieniane na `null` (rodzic poprawia);
  teksty przycinane do 300 znaków. `missing` jest zawsze przeliczane po stronie serwera.
- Limit 5 umów liczy zatwierdzone **i** oczekujące szkice na rodzica (409 przy skanie); szkice starsze niż 24 h są
  usuwane przy kolejnym skanie. Szkic zagubiony po odświeżeniu strony zajmuje miejsce do wygaśnięcia.
- Zatwierdzenie jest jednorazowe (ponowne = 409); inna rodzina i partner dostają 403 (nie 404) przy confirm/delete.
- Aktualizacja profilu przy zatwierdzeniu: wpis `insurance` o tym samym rodzaju i płatniku (porównanie znormalizowane)
  jest uzupełniany (dane z ZUS — podstawa składek, data — mają pierwszeństwo), inaczej dodawany nowy. Usunięcie
  umowy cofa tylko wpis utworzony przez jej zatwierdzenie (ta sama podstawa i data), nigdy wpisu z ZUS.
- Reguły ryzyka: wszystkie wymagają dziecka w drodze z terminem porodu (najwcześniejszy termin). (1) tylko umowa o pracę
  na czas określony, kończąca się przed porodem i nie wcześniej niż dziś; (2) zlecenie z `voluntary_sickness` ≠ `true`
  (także `null` = nie wiadomo), także zlecenia znane tylko z ZUS (bez duplikatu, gdy zeskanowano umowę u tego samego
  płatnika); termin = termin porodu − 90 dni (tylko gdy w przyszłości); (3) zadłużenie z ZUS + JDG (z umowy lub
  z `insurance`), jedno ostrzeżenie na rodzica. Id ostrzeżeń: `reguła:user:źródło:dziecko` (stabilne). Treści prawne
  (art. 177 KP, 90 dni karencji) są orientacyjne — w tekstach jest prośba o weryfikację.
- Demo: `seed/demo_handlers.py` rejestruje się przez import z `routers/contracts.py` (nie edytujemy `seed/__init__`).
  Plan 06 może dopisać własny handler w `seed/demo_chat.py`.
- Frontend: kolejne pliki z jednego uploadu są skanowane po kolei; przy 429/503 kolejne pomijamy.

## Niezweryfikowane
- Brak prawdziwego wywołania Foundry z obrazem (tylko test konwersji wiadomości); `response_format` json_schema
  zależy od wdrożenia.
- `scripts/make_sample_contract.py` wymaga czcionki TTF z polskimi znakami (na macOS Arial); PDF jest zacommitowany.
- Okno wyglądu (branding) sprawdzone tylko w kodzie/testach, bez oglądu w przeglądarce.
