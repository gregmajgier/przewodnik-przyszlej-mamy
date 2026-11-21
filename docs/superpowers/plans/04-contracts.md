# Skan umów i ostrzeżenia o ryzyku — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rodzic wgrywa jedną lub wiele umów, AI wyciąga dane, rodzic zatwierdza; z umów, ZUS i dzieci powstają ostrzeżenia o ryzyku utraty świadczeń.

**Architecture:** `services/contract_extract.py` (tekst PDF/obraz → `ContractDraft` przez `LLM.structured`), `services/risk.py` (czysta funkcja reguł), router `contracts`, widżet ryzyk na dashboardzie.

**Tech Stack:** pypdf, FastAPI `UploadFile`, plan 02 (`ai_guard`, `get_llm`).

**Spec:** §5.2, §10 (ostrzeżenia), §14. Konwencje: `00-conventions.md`. Zależy od 01, 02.

## Global Constraints
- Wiele umów na rodzica (np. etat + zlecenie). Rodzic **zawsze** widzi i zatwierdza wyciągnięte dane przed zapisem do profilu.
- Pola ekstrakcji: `kind` (employment|mandate|jdg), `employer_name`, `employer_address`, `employer_email|None`, `position`, `fte` (0–1), `gross_monthly`, `start_date`, `end_date|None`, `indefinite: bool`, `voluntary_sickness: bool|None`.
- Reguły ryzyka (spec §5.2): (1) umowa na czas określony kończąca się przed `due_date` dziecka → informacja o przedłużeniu do dnia porodu (severity `info`); (2) zlecenie bez dobrowolnego chorobowego → brak zasiłku macierzyńskiego (`high`); (3) JDG z `contribution_debt` → zadłużenie blokuje zasiłek, co zrobić i do kiedy (`high`).
- Limity: maks. 5 MB/plik, maks. 5 umów na rodzica, typy `application/pdf`, `image/png|jpeg`, `text/plain`; endpoint za `ai_guard("contract_scan")`. Treść umowy nie jest logowana.

## Review Focus
- Skan bez tekstu / nieczytelny plik / plik nie-umowa → 422 z polskim komunikatem „Nie udało się odczytać umowy…”, brak zapisu.
- Model zwraca brakujące pola → `draft` z `null` i `missing: [..]` do uzupełnienia przez rodzica.
- Dwie umowy tego samego rodzica (etat + zlecenie) — ryzyka liczone dla każdej, bez duplikatów.
- Rodzic A nie widzi surowego pliku rodzica B, ale widzi zatwierdzone dane (zgodnie ze specem: oboje widzą wszystko → dane tak, plik źródłowy tylko właściciel).
- Plik złośliwy (nagłówek ≠ typ, PDF z JS) — odrzucony po sniffingu magic bytes.

---

### Task 1: Modele i reguły ryzyka
**Files:** Create `backend/app/models/contract.py`, `backend/app/services/risk.py`, `backend/tests/test_risk.py`.
**Interfaces:** Produces
```python
class ContractDraft(BaseModel): kind|None; employer_name|None; employer_address|None; employer_email|None; position|None; fte|None; gross_monthly|None; start_date|None; end_date|None; indefinite|None; voluntary_sickness|None; missing: list[str] = []
class Contract(ContractDraft): id; user_id; family_id; filename; confirmed: bool; created_at   # po zatwierdzeniu pola wymagane
class Risk(BaseModel): id: str; severity: Literal["info","medium","high"]; title: str; explanation: str; action: str|None; deadline: date|None; user_id: str; source_ref: str
def evaluate_risks(profile: ParentProfile, contracts: list[Contract], children: list[Child], today: date) -> list[Risk]
```
- [ ] Testy: `test_fixed_term_ending_before_due_date_info`, `test_fixed_term_ending_after_due_date_no_risk`, `test_indefinite_contract_no_risk`, `test_mandate_without_voluntary_sickness_high`, `test_mandate_with_voluntary_sickness_ok`, `test_jdg_debt_high_with_action`, `test_no_expected_child_no_pregnancy_risks`, `test_two_contracts_independent_risks`, `test_risk_ids_stable` (ten sam input → te same `id`). Commit.

### Task 2: Ekstrakcja umowy
**Files:** Create `backend/app/services/contract_extract.py`, `backend/tests/test_contract_extract.py`, `backend/scripts/make_sample_contract.py` (generuje `backend/app/seed/sample_umowa_anna_nowak.pdf` z `fpdf2`; dodaj `fpdf2` do `requirements-dev.txt`), `backend/app/seed/demo_handlers.py` (rejestruje `register_demo_handler("contract_scan", ...)` zwracający dane Anny Nowak wyliczone z tekstu pliku przez proste regexy: „umowa o pracę”/„zlecenie”).
**Interfaces:** Consumes `LLM.structured`. Produces `async def extract_contract(llm: LLM, filename: str, content: bytes, content_type: str) -> ContractDraft`; `def detect_type(content: bytes) -> Literal["pdf","png","jpeg","text"] | None` (magic bytes).
- [ ] Testy z `FakeLLM`: `test_pdf_text_passed_to_llm`, `test_missing_fields_listed`, `test_unreadable_pdf_raises_unreadable`, `test_detect_type_rejects_exe_renamed_pdf`, `test_image_sent_as_image_part` (message zawiera część obrazu), `test_demo_handler_extracts_anna_contract_from_sample_pdf`. Commit.

### Task 3: API umów
**Files:** Create `backend/app/routers/contracts.py`, `backend/tests/test_contracts_api.py`, `backend/app/tools/contracts.py`.
**Interfaces:** `POST /api/contracts/scan` (multipart `file`) → `{draft_id, draft: ContractDraft, filename}` (draft zapisany jako `confirmed=false`); `POST /api/contracts/{id}/confirm` (body: poprawiony `ContractDraft`) → `Contract` (waliduje wymagane: kind, employer_name, start_date, fte lub gross_monthly); i aktualizuje `ParentProfile.insurance` (dodaje/łączy wpis zgodny z umową); `GET /api/contracts` (zatwierdzone umowy rodziny); `DELETE /api/contracts/{id}` (właściciel); `GET /api/risks` (ryzyka rodziny); narzędzie MCP `ryzyka`.
- [ ] Testy: `test_scan_requires_ai_guard_limit_429`, `test_scan_rejects_too_large_413`, `test_confirm_requires_required_fields_422`, `test_confirm_updates_profile_insurance`, `test_limit_5_contracts_409`, `test_other_family_forbidden`, `test_partner_sees_confirmed_data_not_file`, `test_risks_endpoint_uses_contracts_and_zus`. Commit.

### Task 4: Frontend
**Files:** Create `frontend/src/features/contracts/{routes.tsx,ContractsPage.tsx,ContractUpload.tsx,ContractReview.tsx,widget.tsx,RisksPanel.tsx}`, testy.
**Interfaces:** Trasa `/umowy` (lista + dodawanie), krok „Umowy” w onboardingu (opcjonalny — eksportuj `ContractUpload` do użycia w `OnboardingPage` przez dynamiczny import trasy `/start/umowy`, bez edycji plików planu 01: dodaj własną trasę), `widget.tsx` (`order: 20`) pokazuje ryzyka z `/api/risks` (kolor wg `severity`, akcja i termin).
- [ ] `ContractReview`: formularz edytowalny z polami draftu, pola `missing` podświetlone; „Zatwierdź” wywołuje confirm; błędy limitu 429 pokazują komunikat z API.
- [ ] Testy: upload → review pokazuje wyciągnięte dane; brakujące pola podświetlone; zatwierdzenie wywołuje confirm; widżet bez ryzyk pokazuje „Brak ostrzeżeń”. Commit.

### Task 5: Weryfikacja
- [ ] Pełne testy i build zielone; `docs/dev.md`: jak wygenerować przykładową umowę i przetestować skan w trybie demo. Commit.
