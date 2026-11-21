# Świadczenia, dopasowanie, analiza i dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Katalog świadczeń (krajowe + lokalne), deterministyczny silnik dopasowania z wyjaśnieniami, ekran „analizy” po onboardingu i dashboard z kafelkami.

**Architecture:** Model `Benefit` z kryteriami strukturalnymi i listą warunków dodatkowych; czysta funkcja `match_benefit(ctx, benefit)`; seed krajowy z JSON; frontend: `/analiza`, `/` (dashboard z widgetami), `/swiadczenia`.

**Tech Stack:** FastAPI/pydantic, React.

**Spec:** §6, §7.1, §7.3, §11. Konwencje: `00-conventions.md`. Zależy od planów 01, 02.

## Global Constraints
- Statusy dopasowania: `fits` („pasuje”), `maybe` („może ci przysługiwać”), `no` („nie pasuje”, z powodem). Niepasujące widoczne, ale schowane za „Pokaż pozostałe”.
- Każde dopasowanie ma `reasons` (np. „pasuje, bo dziecko ma 3 lata i mieszkasz w Krakowie”) i, dla `maybe`, `questions` tak/nie; odpowiedzi zapisują się w `ParentProfile.answers` (nie pytać drugi raz).
- Dashboard pokazuje stawki z `GET /api/parametry` z etykietą *„Parametry ZUS 2026 – aktywne”*.
- Każde świadczenie ma `source_url`; dane niepewne oznacz `verify: true`.
- LLM nie działa przy dopasowywaniu (tylko przy publikacji świadczenia gminnego — plan 07).

## Review Focus
- Dziecko dokładnie na granicy wieku (np. kończy 18 lat dziś; 3 lata minus 1 dzień) — granice włącznie/wyłącznie zdefiniowane i przetestowane.
- Rodzina bez dzieci urodzonych (tylko „w drodze”) — świadczenia dla ciąży pasują, a 800+ pokazuje „po urodzeniu”.
- Trzecie dziecko po porodzie odblokowuje KDR i 3+ (zmiana `status` dziecka przelicza dopasowanie).
- Dochód na członka: brak danych o dochodzie → `maybe` + pytanie, nie `no`.
- Świadczenie gminne innej gminy nigdy nie pojawia się rodzinie z Krakowa; wojewódzkie widzą wszystkie gminy województwa.

---

### Task 1: Model i pokrycie jednostek
**Files:** Create `backend/app/models/benefit.py`, `backend/app/services/units.py`, `backend/tests/test_units.py`.
**Interfaces:** Produces
```python
class Criteria(BaseModel): child_age_min_months: int|None; child_age_max_months: int|None; max_income_per_person: float|None; min_children: int|None; requires_pregnancy: bool|None; requires_disability: bool|None; requires_foster: bool|None; employment_kinds: list[Literal["employment","mandate","jdg"]]|None
class Condition(BaseModel): id: str; text: str; kind: Literal["auto","ask"]; question: str|None; profile_key: str|None   # auto → sprawdzane po profile_key
class Deadline(BaseModel): anchor: Literal["birth","due","child_age","fixed"]; offset_days: int|None; offset_months: int|None; fixed_date: date|None; note: str|None
class Benefit(BaseModel): id; name; scope: Literal["national","regional","municipal"]; unit_id: str|None; category: Literal["benefit","perk"]; description; amount_text|None; annual_value_estimate: int|None; deadline: Deadline|None; how_to_apply: str; form_codes: list[str]; source_url: str; criteria: Criteria; extra_conditions: list[Condition]; extra_text: str|None; status: Literal["draft","published"]; verify: bool=False
def covers(unit: dict, address: Address) -> bool        # gmina: gmina==; powiat; voivodeship; national → True
def units_for(address, units: list[dict]) -> list[str]
```
- [ ] Testy: `test_gmina_covers_only_own_gmina`, `test_voivodeship_covers_all_gminas_in_it`, `test_national_covers_everyone`. Commit.

### Task 2: Silnik dopasowania
**Files:** Create `backend/app/services/matching.py`, `backend/tests/test_matching.py`.
**Interfaces:** Consumes `Benefit`, `ParentProfile`, `Child`. Produces
```python
class FamilyContext(BaseModel): children: list[Child]; parents: list[ParentProfile]; today: date; address: Address; answers: dict
def build_context(family_view, profiles, today) -> FamilyContext
class MatchResult(BaseModel): status: Literal["fits","maybe","no"]; reasons: list[str]; unmet: list[str]; questions: list[Question(condition_id,text)]
def match_benefit(ctx: FamilyContext, benefit: Benefit) -> MatchResult
def age_in_months(birth: date, today: date) -> int
```
- [ ] Testy tabelaryczne (parametryzowane): wiek 0/35/36 miesięcy względem `min/max`, granice włącznie; `test_pregnancy_requires_expected_child`; `test_min_children_counts_expected_after_birth_only`; `test_income_unknown_gives_maybe_with_question`; `test_ask_condition_answered_true_fits`, `…_false_no`; `test_auto_condition_uses_profile_key`; `test_reasons_are_human_readable_polish`; `test_other_municipality_is_no_with_reason`.
- [ ] Reguły: dowolne niespełnione kryterium strukturalne → `no`; wszystkie spełnione i brak nierozstrzygniętych warunków → `fits`; spełnione + nierozstrzygnięte `ask` → `maybe`. Commit.

### Task 3: Seed świadczeń krajowych
**Files:** Create `backend/app/data/benefits_national.json`, `backend/app/seed/benefits.py` (ładuje JSON → `benefits` w `seed_all`), `backend/tests/test_benefits_seed.py`; podłącz w `seed_all` (jedna linia w `app/seed/__init__.py`).
- [ ] Zbadaj oficjalne źródła (ZUS, gov.pl, MRPiPS, ISAP) i przygotuj **co najmniej 16 pozycji**: zasiłek macierzyński; urlop macierzyński/rodzicielski/ojcowski (jako `perk`/benefit z powiązaniem `form_codes`); zasiłek chorobowy w ciąży (e-ZLA B); 800+; Aktywny rodzic (3 warianty: w pracy, w żłobku, w domu); jednorazowa „becikowe” 1000 zł; „Za życiem” 4000 zł; zasiłek rodzinny + dodatki; Dobry Start 300+; Karta Dużej Rodziny (3+); ulga prorodzinna (PIT); bezpłatne leki dla kobiet w ciąży (jeśli aktualne); świadczenie pielęgnacyjne/zasiłek pielęgnacyjny (niepełnosprawność); rodziny zastępcze (dodatek); darmowe badania prenatalne; bon żłobkowy/dofinansowanie żłobka. Kwoty i kryteria z oficjalnych źródeł; `source_url` obowiązkowy; wątpliwe → `verify: true`.
- [ ] Testy: każdy rekord waliduje się modelem, ma `source_url` `https://`, unikalne `id`, `form_codes` istnieją w `katalog_wnioskow_pdf.json` (lub puste), ≥16 pozycji, `test_nowak_family_fits_expected_benefits` (rodzina Nowaków przed porodem: pasuje m.in. zasiłek macierzyński, e-ZLA B, Aktywny rodzic dla 3-latka lub „maybe”; po zmianie dziecka w drodze na `born` pojawia się KDR). Commit.

### Task 4: API świadczeń, analiza, podsumowanie
**Files:** Create `backend/app/routers/benefits.py`, `backend/app/services/benefit_service.py`, `backend/tests/test_benefits_api.py`; `backend/app/tools/benefits.py`.
**Interfaces:** Produces `GET /api/benefits -> [{benefit, match}]` (tylko `published`, z uwzględnieniem `covers` po adresie rodziny), `GET /api/benefits/{id}`, `POST /api/benefits/{id}/answers {condition_id, answer: bool}` (zapis do `profile.answers["benefit:{id}:{cid}"]`), `GET /api/analysis -> {steps:[{key,label,detail,status}], totals:{national,local,fits,maybe,no}, estimated_annual_total, nearest_deadline}` (liczby z faktycznego wyniku silnika), `GET /api/summary` (do dashboardu: ta sama agregacja + `parameters_label`); narzędzie MCP `swiadczenia` (parametry: `status?: fits|maybe|no`) rejestrowane w `app/tools/benefits.py` przez `@tool` z planu 02.
- [ ] Testy API: `test_benefits_list_requires_parent`, `test_answer_changes_maybe_to_fits`, `test_analysis_counts_match_list`, `test_other_family_answers_not_shared`, `test_local_benefit_visible_only_in_area`, `test_tool_swiadczenia_returns_matches`.
- [ ] Commit.

### Task 5: Frontend — analiza, dashboard, lista świadczeń
**Files:** Create `frontend/src/features/analysis/{routes.tsx,AnalysisPage.tsx}`, `features/dashboard/{routes.tsx,nav.ts,DashboardPage.tsx,widgets.ts}`, `features/benefits/{routes.tsx,nav.ts,BenefitsPage.tsx,BenefitCard.tsx,widget.tsx}`; testy obok.
**Interfaces:** Consumes `/api/analysis`, `/api/summary`, `/api/benefits`, wspólny `widgets` z registry (plan 01). Dashboard: nagłówek z podsumowaniem (liczba świadczeń, szac. kwota roczna, najbliższy termin, etykieta *Parametry ZUS 2026 – aktywne*), siatka widgetów posortowana po `order`.
- [ ] `AnalysisPage`: kroki z `/api/analysis` ujawniane kolejno co ~700 ms (ostatni „⟳” zamienia się w „✓”), `prefers-reduced-motion` → od razu wszystko; na końcu przycisk „Przejdź do panelu”. Testy z fake timers: kolejność kroków, liczby z API, reduced-motion.
- [ ] `BenefitCard`: nazwa, status-badge, „dlaczego”, kwota, link do źródła, przycisk „Złóż wniosek” (gdy `form_codes` niepuste; trasa `/wnioski/nowy?form=KOD` dostarcza plan 08), dla `maybe` pytania tak/nie. `BenefitsPage`: grupy fits/maybe oraz zwijane „Pozostałe”.
- [ ] Po zakończeniu onboardingu (plan 01) przekierowanie na `/analiza`, potem `/`. Zmień przekierowanie `/` → dashboard (zastępuje tymczasowe `/rodzina`). Commit.

### Task 6: Weryfikacja
- [ ] `pytest -q`, `npm test -- --run && npm run lint && npm run build` zielone. Uzupełnij `docs/dev.md` o opis katalogu i jak dodać świadczenie. Commit.
