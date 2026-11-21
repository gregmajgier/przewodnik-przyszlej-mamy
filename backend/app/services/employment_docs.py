"""Umowy z „e-teczki pracodawcy” (dane demo): lista dla rodzica, PDF generowany na żądanie i dodanie do umów.

Umowy są przypisane do persony (`employment_docs` w `app/seed/personas.py`), więc każdy rodzic widzi wyłącznie
swoje. PDF nie jest przechowywany — generujemy go deterministycznie z tych samych danych, z których powstaje
zatwierdzona umowa, więc treść dokumentu i dane widoczne w aplikacji (i dla asystenta AI) zawsze się zgadzają.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from fpdf import FPDF

from ..errors import DomainError
from ..models.contract import ContractDraft, EmploymentDocument
from ..seed.personas import get_persona
from ..storage import Store
from .employer_pdf import FONT_DIR

NOT_FOUND = "Nie znaleziono takiego dokumentu."

TITLES = {
    "employment": "Umowa o pracę",
    "mandate": "Umowa zlecenia",
    "jdg": "Umowa o współpracy (B2B)",
}


@dataclass(frozen=True)
class SourceDoc:
    id: str
    draft: ContractDraft
    signed_on: date
    first_name: str
    last_name: str
    city: str
    home_address: str
    female: bool

    @property
    def title(self) -> str:
        period = "na czas nieokreślony" if self.draft.indefinite else "na czas określony"
        base = TITLES[self.draft.kind or "employment"]
        return f"{base} {period}" if self.draft.kind == "employment" else base

    @property
    def filename(self) -> str:
        employer = "".join(ch for ch in (self.draft.employer_name or "").split(" ")[0] if ch.isalnum())
        return f"{self.id}_{self.last_name}_{employer}.pdf".replace(" ", "_")


async def _persona_id(store: Store, user_id: str) -> str | None:
    user = await store.get("users", user_id)
    return user.get("persona_id") if user else None


def _docs_for_persona(persona_id: str | None, today: date) -> list[SourceDoc]:
    persona = get_persona(persona_id) if persona_id else None
    if persona is None:
        return []
    z = persona["zus"]
    a = z["address"]
    out: list[SourceDoc] = []
    for spec in persona.get("employment_docs", []):
        start = today - timedelta(days=spec["start_days_ago"])
        end = today + timedelta(days=spec["end_in_days"]) if spec.get("end_in_days") is not None else None
        draft = ContractDraft(
            kind=spec["kind"],
            employer_name=spec["employer_name"],
            employer_address=spec.get("employer_address"),
            employer_email=spec.get("employer_email"),
            position=spec.get("position"),
            fte=spec.get("fte"),
            gross_monthly=spec.get("gross_monthly"),
            start_date=start,
            end_date=end,
            indefinite=end is None,
            voluntary_sickness=spec.get("voluntary_sickness"),
        )
        out.append(
            SourceDoc(
                id=spec["id"],
                draft=draft,
                signed_on=start - timedelta(days=7),
                first_name=z["first_name"],
                last_name=z["last_name"],
                city=a["city"],
                home_address=f"{a['postal_code']} {a['city']}",
                female=bool(z.get("female")),
            )
        )
    return out


async def user_source_docs(store: Store, user_id: str, today: date) -> list[SourceDoc]:
    return _docs_for_persona(await _persona_id(store, user_id), today)


async def get_source_doc(store: Store, user_id: str, doc_id: str, today: date) -> SourceDoc:
    for doc in await user_source_docs(store, user_id, today):
        if doc.id == doc_id:
            return doc
    raise DomainError(404, NOT_FOUND)


async def list_documents(store: Store, user_id: str, today: date) -> list[EmploymentDocument]:
    imported = {
        c["source_doc_id"]: c["id"]
        for c in await store.find("contracts", user_id=user_id)
        if c.get("source_doc_id") and c.get("confirmed")
    }
    return [
        EmploymentDocument(
            id=d.id,
            title=d.title,
            filename=d.filename,
            kind=d.draft.kind,
            employer_name=d.draft.employer_name,
            position=d.draft.position,
            fte=d.draft.fte,
            gross_monthly=d.draft.gross_monthly,
            start_date=d.draft.start_date,
            end_date=d.draft.end_date,
            indefinite=bool(d.draft.indefinite),
            voluntary_sickness=d.draft.voluntary_sickness,
            contract_id=imported.get(d.id),
        )
        for d in await user_source_docs(store, user_id, today)
    ]


# --- PDF ------------------------------------------------------------------------------------------------


def _d(value: date | None) -> str:
    return value.strftime("%d.%m.%Y") if value else "—"


def _money(v: float | None) -> str:
    if v is None:
        return "—"
    whole, frac = f"{v:,.2f}".split(".")
    return f"{whole.replace(',', '\u00a0')},{frac}\u00a0zł"


def _fte(v: float | None) -> str:
    if v is None:
        return "—"
    return "pełny etat" if v >= 1 else f"{v:g} etatu".replace(".", ",")


def _mandate_paragraphs(doc: SourceDoc) -> list[tuple[str, str]]:
    d = doc.draft
    sickness = (
        "Zleceniobiorca wnosi o objęcie go dobrowolnym ubezpieczeniem chorobowym, a Zleceniodawca zgłosi go do tego "
        "ubezpieczenia w ZUS."
        if d.voluntary_sickness
        else "Zleceniobiorca nie wnosi o objęcie go dobrowolnym ubezpieczeniem chorobowym."
    )
    return [
        (
            "§ 1. Przedmiot umowy",
            f"Zleceniodawca zleca, a Zleceniobiorca przyjmuje do wykonania: {(d.position or '—').lower()}. "
            "Zleceniobiorca wykonuje zlecenie osobiście, w terminach uzgodnionych ze Zleceniodawcą.",
        ),
        ("§ 2. Okres obowiązywania", f"Umowa obowiązuje od dnia {_d(d.start_date)} do dnia {_d(d.end_date)}."),
        (
            "§ 3. Wynagrodzenie",
            f"Za wykonanie zlecenia Zleceniobiorcy przysługuje wynagrodzenie w wysokości {_money(d.gross_monthly)} "
            "brutto miesięcznie, płatne na podstawie rachunku do 10. dnia następnego miesiąca.",
        ),
        ("§ 4. Ubezpieczenia", sickness),
        (
            "§ 5. Postanowienia końcowe",
            "W sprawach nieuregulowanych umową zastosowanie mają przepisy Kodeksu cywilnego (art. 734 i nast.). "
            "Umowę sporządzono w dwóch jednobrzmiących egzemplarzach, po jednym dla każdej ze stron.",
        ),
    ]


def contract_paragraphs(doc: SourceDoc) -> list[tuple[str, str]]:
    d = doc.draft
    if d.kind == "mandate":
        return _mandate_paragraphs(doc)
    period = (
        f"Umowa zostaje zawarta na czas nieokreślony, począwszy od dnia {_d(d.start_date)}."
        if d.indefinite
        else f"Umowa zostaje zawarta na czas określony od dnia {_d(d.start_date)} do dnia {_d(d.end_date)}."
    )
    return [
        ("§ 1. Rodzaj umowy", period),
        (
            "§ 2. Warunki pracy",
            f"Pracownik zostaje zatrudniony na stanowisku: {d.position or '—'}, w wymiarze czasu pracy: "
            f"{_fte(d.fte)}. Miejscem wykonywania pracy jest siedziba Pracodawcy ({d.employer_address or '—'}).",
        ),
        (
            "§ 3. Wynagrodzenie",
            f"Pracownikowi przysługuje wynagrodzenie zasadnicze w wysokości {_money(d.gross_monthly)} brutto "
            "miesięcznie, płatne z dołu do 10. dnia następnego miesiąca na rachunek bankowy wskazany przez Pracownika.",
        ),
        (
            "§ 4. Czas pracy i urlop",
            "Czas pracy wynosi 8 godzin na dobę i przeciętnie 40 godzin w przeciętnie pięciodniowym tygodniu pracy. "
            "Pracownikowi przysługuje urlop wypoczynkowy w wymiarze wynikającym z art. 154 Kodeksu pracy.",
        ),
        (
            "§ 5. Uprawnienia rodzicielskie",
            "Pracownikowi przysługują uprawnienia związane z rodzicielstwem określone w Dziale VIII Kodeksu pracy, "
            "w tym urlop macierzyński, ojcowski i rodzicielski oraz zwolnienie od pracy na opiekę nad dzieckiem "
            "(art. 188 Kodeksu pracy). Wnioski w tych sprawach Pracownik składa w dziale kadr "
            f"({d.employer_email or 'kadry'}).",
        ),
        (
            "§ 6. Postanowienia końcowe",
            "W sprawach nieuregulowanych umową zastosowanie mają przepisy Kodeksu pracy. Umowę sporządzono "
            "w dwóch jednobrzmiących egzemplarzach, po jednym dla każdej ze stron.",
        ),
    ]


def render_pdf(doc: SourceDoc) -> bytes:
    d = doc.draft
    pdf = FPDF(format="A4")
    pdf.set_margins(25, 22, 25)
    pdf.set_auto_page_break(True, margin=22)
    pdf.add_font("DejaVu", "", str(FONT_DIR / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", str(FONT_DIR / "DejaVuSans-Bold.ttf"))
    pdf.set_title(doc.title)
    pdf.set_author(d.employer_name or "")
    pdf.add_page()
    w = pdf.epw

    pdf.set_font("DejaVu", "B", 15)
    pdf.cell(w, 9, doc.title.upper(), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 10)
    pdf.cell(w, 6, f"zawarta w dniu {_d(doc.signed_on)} w miejscowości {doc.city}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    pdf.set_font("DejaVu", "", 11)
    pdf.multi_cell(w, 6, "pomiędzy:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "B", 11)
    pdf.multi_cell(w, 6, d.employer_name or "", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 11)
    mandate = d.kind == "mandate"
    side_a, side_b = ("Zleceniodawcą", "Zleceniobiorcą") if mandate else ("Pracodawcą", "Pracownikiem")
    pdf.multi_cell(w, 6, f"z siedzibą: {d.employer_address or '—'}, zwaną dalej „{side_a}”,", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.multi_cell(w, 6, "a", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "B", 11)
    pdf.multi_cell(w, 6, f"{doc.first_name} {doc.last_name}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 11)
    called = "zwaną" if doc.female else "zwanym"
    pdf.multi_cell(w, 6, f"zam. {doc.home_address}, {called} dalej „{side_b}”.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    for heading, text in contract_paragraphs(doc):
        pdf.set_font("DejaVu", "B", 11)
        pdf.multi_cell(w, 6, heading, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("DejaVu", "", 10.5)
        pdf.multi_cell(w, 5.6, text, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    pdf.ln(16)
    y = pdf.get_y()
    labels = ("Zleceniodawca", "Zleceniobiorca") if mandate else ("Pracodawca", "Pracownik")
    for i, label in enumerate(labels):
        x = pdf.l_margin + i * w / 2
        pdf.set_xy(x, y)
        pdf.set_font("DejaVu", "", 10)
        pdf.cell(w / 2, 6, "……………………………………", align="C")
        pdf.set_xy(x, y + 6)
        pdf.set_font("DejaVu", "", 9)
        pdf.cell(w / 2, 5, label, align="C")
    pdf.set_xy(pdf.l_margin, y + 20)
    pdf.set_font("DejaVu", "", 7.5)
    pdf.multi_cell(
        w,
        3.8,
        "Dokument demonstracyjny wygenerowany w aplikacji mRodzina (e-teczka pracodawcy). Dane są fikcyjne.",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    return bytes(pdf.output())
