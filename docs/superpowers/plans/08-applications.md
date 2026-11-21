# Wnioski: wypełnianie, agent w makiecie portalu, wysyłka — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rodzic składa wniosek z wstępnie wypełnionymi danymi: PDF (AcroForm lub generowany do pracodawcy) albo agent „klika” w makiecie eZUS/Emp@tii; zatwierdza; wniosek jest wysyłany (e-mail do pracodawcy przez symulowaną skrzynkę, portal przez makietę).

**Architecture:** `services/prefill.py` mapuje zmienne profilu (`zmienne_uzytkownika.json`) na pola formularzy; `services/pdf_fill.py` (pypdf AcroForm) i `services/employer_pdf.py` (`fpdf2`, wzór wg rozporządzenia MRPiPS Dz.U. 2025 poz. 322); `services/agent_plan.py` (LLM → plan pole→wartość walidowany względem schematu portalu); `mail/provider.py` (interfejs + `SimMailProvider` — strona wysyłki); makiety portali jako trasy frontendu `/sim/*` w iframe, sterowane `postMessage`.

**Spec:** §8. Konwencje: `00-conventions.md`. Zależy od 01, 02, 03.

## Global Constraints
- Kanały z katalogu `backend/app/data/katalog_wnioskow_pdf.json`: pracodawca → PDF generowany + e-mail; ZUS i gmina → agent w makiecie lub PDF do pobrania; `tylko_elektronicznie: true` (800+, Aktywny rodzic) → tylko agent.
- Rozgałęzienie (diagram 3): pracownik → najpierw wniosek o urlop do pracodawcy; zlecenie/JDG → od razu ZAM. Funkcja `recommend_flow(insurance_kind) -> list[form_code]`.
- **Zawsze** podgląd i zatwierdzenie przez rodzica przed wysyłką. Wnioskodawcą jest zalogowany rodzic; dane drugiego rodzica i dzieci z profilu rodziny.
- AI dopytuje tylko o brakujące dane, odpowiedzi zapisują się w profilu (nie pytać drugi raz). Agent zatrzymuje się przy brakach i przed wysłaniem; rodzic może przejąć i edytować pole.
- Podpis gov = **symulowany** krok (modal „Podpisz Profilem Zaufanym”) przed wysyłką PDF.
- Plan agenta za `ai_guard("agent_plan")`; PDF-y i dane wniosków nie trafiają do logów.

## Review Focus
- Brak wymaganych danych (np. PESEL dziecka w drodze) → wniosek `needs_input`, nie crash ani puste pole w PDF.
- Plan agenta z polem spoza schematu portalu / wartością niezgodną z typem → odrzucone, nie wstrzykiwane do iframe.
- Rodzic próbuje złożyć wniosek dla dziecka cudzej rodziny → 404.
- Podwójne kliknięcie „Wyślij” → jedna wysyłka (idempotencja po `application.id`).
- PDF AcroForm: pole nieistniejące w formularzu w mapie → test wykrywa rozjazd mapy z PDF.
- Dziecko w trybie straty (`situation=loss`) → szkice dla niego blokowane/anulowane (współpraca z planem 10: eksponuj `cancel_drafts_for_child(child_id)`).

---

### Task 1: Mapy pól i prefill
**Files:** Create `backend/app/data/form_field_maps/{ZAM,ZAS-53,ZAS-26,ZAS-33,Z-3,Z-3a,ZAS-39,ZAS-55,ZNp-7,Z-10}.json` (pole PDF → klucz zmiennej profilu), `backend/app/services/prefill.py`, `backend/tests/test_prefill.py`.
**Interfaces:** Produces `FormField(id, label, type: text|date|bool|choice, required, source_key|None)`; `def form_schema(code) -> list[FormField]`; `def prefill(code, family_view, profiles, child_id|None, answers: dict) -> PrefillResult(values: dict[str,Any], missing: list[Question(field_id,label,type)])`; `def recommend_flow(insurance_kind) -> list[str]`.
- [ ] Najpierw zbadaj AcroForm: `pypdf.PdfReader(...).get_fields()` dla każdego PDF-a w `backend/app/data/wnioski_pdf/*wypelnij*` i zapisz nazwy; mapy buduj z rzeczywistych nazw pól.
- [ ] Testy: `test_map_fields_exist_in_pdf` (dla każdej mapy każde pole istnieje w PDF), `test_prefill_zam_from_nowak_anna`, `test_missing_pesel_listed`, `test_answers_fill_missing`, `test_recommend_flow_employee_urlop_then_zam`, `test_recommend_flow_mandate_zam_only`, `test_other_family_child_404`. Commit.

### Task 2: Generowanie i wypełnianie PDF
**Files:** Create `backend/app/services/pdf_fill.py`, `backend/app/services/employer_pdf.py`, `backend/tests/test_pdf.py`.
**Interfaces:** `def fill_pdf(code: str, values: dict) -> bytes` (AcroForm, `NeedAppearances=True`); `def render_employer_application(kind: Literal["URLOP-MAC-ROD","URLOP-ROD","URLOP-OJC","URLOP-UZUP","URLOP-ROD-PRACA","REZYGNACJA-MAC"], data: EmployerData) -> bytes` (PDF z polskimi znakami — font Unicode dołączony do repo, np. DejaVu/Noto Sans; treść wg wzorów z rozporządzenia, w tym termin i dane pracodawcy).
- [ ] Testy: wypełniony PDF zawiera wartości (odczyt `get_fields()`), `test_employer_pdf_has_polish_diacritics_and_dates` (tekst z `pypdf.extract_text`), `test_unknown_code_raises`. Commit.

### Task 3: Model wniosku, API, wysyłka, MailProvider
**Files:** Create `backend/app/models/application.py`, `backend/app/mail/__init__.py`, `backend/app/mail/provider.py`, `backend/app/routers/applications.py`, `backend/tests/test_applications.py`.
**Interfaces:** Produces `Application(id, family_id, applicant_id, form_code, child_id|None, channel: "employer_email"|"portal_agent"|"pdf_download", status: draft|needs_input|ready|sent|received|more_info|accepted|rejected, values, missing, recipient_email|None, recipient_domain|None, thread_id|None, sent_at|None, created_at)`; `MailProvider(Protocol): async def send(family_id, from_user_id, to, subject, body, attachments:[(filename,bytes)]) -> SentMessage(thread_id,message_id); async def list_messages(family_id) -> list[MailMessage]`; `SimMailProvider(store)` zapisuje do `mail_messages` (folder `sent`); `get_mail() -> MailProvider`; endpointy `GET /api/applications/forms` (katalog + kanał + rekomendowana kolejność), `GET|POST /api/applications` (`{form_code, child_id?}` → draft z prefill), `GET|PATCH /api/applications/{id}`, `POST /api/applications/{id}/answers`, `GET /api/applications/{id}/pdf` (podgląd), `POST /api/applications/{id}/sign` (symulowany podpis), `POST /api/applications/{id}/submit` (idempotentny), `POST /api/applications/{id}/agent-plan`, `POST /api/applications/{id}/portal-submitted` (callback z makiety); funkcja `cancel_drafts_for_child(store, child_id) -> int`.
- [ ] Testy: `test_create_draft_prefills`, `test_submit_employer_sends_mail_with_pdf_attachment_and_stores_thread`, `test_submit_twice_sends_once`, `test_submit_needs_input_409`, `test_submit_pdf_channel_requires_sign`, `test_cancel_drafts_for_child`, `test_tylko_elektronicznie_rejects_pdf_channel`, `test_applicant_is_logged_in_parent`, `test_partner_sees_application_in_family_list`. Commit.

### Task 4: Plan agenta
**Files:** Create `backend/app/data/portal_schemas.json` (pola makiet: `ezus_800plus`, `ezus_aktywny_rodzic`, `ezus_zam`, `emp_kdr`, `emp_za_zyciem`), `backend/app/services/agent_plan.py`, `backend/app/seed/demo_agent.py`, `backend/tests/test_agent_plan.py`.
**Interfaces:** `class PlanStep(field_id, value, reason)`; `async def build_plan(llm, portal_id, prefill: PrefillResult) -> AgentPlan(steps, blocked: list[Question])` (kroki tylko dla pól ze schematu, wartości walidowane typem/wyborem; brak wartości → `blocked`, nie zgadywanie).
- [ ] Testy z `FakeLLM`: `test_steps_only_for_schema_fields`, `test_invalid_value_for_choice_dropped`, `test_missing_required_goes_to_blocked`, `test_demo_handler_builds_plan_from_prefill_without_llm`. Commit.

### Task 5: Frontend — kreator wniosku
**Files:** Create `frontend/src/features/applications/{routes.tsx,nav.ts,ApplicationsPage.tsx,NewApplicationPage.tsx,ApplicationWizard.tsx,MissingFieldsStep.tsx,PreviewStep.tsx,SignModal.tsx}`, testy.
**Interfaces:** Trasy `/wnioski` (lista z statusami i „kto złożył”), `/wnioski/nowy?form=KOD` (kreator): 1) brakujące dane (pytania po jednym, zapis w profilu), 2) podgląd (PDF w `<iframe>`/lista pól), 3) kanał: e-mail do pracodawcy (adres z umowy lub pole), podpis (modal symulacji), albo agent (Task 6); 4) wysłano + link do kalendarza i poczty.
- [ ] Testy: kreator przechodzi kroki z mockiem API; brak danych blokuje przejście; „Wyślij” wyłącza przycisk po kliknięciu. Commit.

### Task 6: Makiety portali i agent w iframe
**Files:** Create `frontend/src/features/portal-sim/{routes.tsx,EzusForm.tsx,EmpatiaForm.tsx,agentBridge.ts,AgentFrame.tsx,AgentCursor.tsx}`, testy.
**Interfaces:** Trasy publiczne `/sim/ezus/:portalId`, `/sim/empatia/:portalId` renderują formularze wg `portal_schemas.json` (te same `field_id`; wyraźny znacznik „SYMULACJA — to nie jest prawdziwy portal”, osobny kolor „AI/symulacja” z legendy). `agentBridge.ts`: protokół `postMessage` `{type:'fill', fieldId, value}` → ack, `{type:'ready'}`, `{type:'submitted'}`; sprawdza `event.origin === location.origin`. `AgentFrame` osadza iframe, pobiera plan (`/agent-plan`), wykonuje kroki sekwencyjnie z widocznym kursorem i podświetleniem (`prefers-reduced-motion` → bez animacji ruchu), zatrzymuje się na `blocked` (pyta rodzica) i przed wysłaniem (przycisk „Zatwierdzam i wysyłam”); rodzic może edytować pole w iframe; po `submitted` woła `portal-submitted`.
- [ ] Testy: `agentBridge` odrzuca wiadomości z obcego origin; `AgentFrame` wykonuje plan w kolejności (mock iframe); zatrzymuje się na `blocked`; nie wysyła bez zatwierdzenia. Commit.

### Task 7: Weryfikacja
- [ ] Testy i build zielone; przejście ręcznego scenariusza przez API w teście integracyjnym `tests/test_flow_application_e2e.py` (Anna: ZAM/urlop → draft → answers → sign → submit → mail w `sent`). `docs/dev.md`. Commit.
