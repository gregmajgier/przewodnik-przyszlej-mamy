"""Deterministyczny silnik dopasowania świadczeń (bez LLM).

Zasady:
- dowolne niespełnione kryterium strukturalne lub odrzucony warunek -> `no` (z powodem),
- wszystko spełnione i brak nierozstrzygniętych warunków -> `fits`,
- wszystko spełnione, ale są nierozstrzygnięte warunki (`ask`, brak dochodu) -> `maybe` + pytania tak/nie.

Wiek dziecka = liczba pełnych ukończonych miesięcy; granice kryteriów włącznie.
Dziecko „w drodze” (`status=expected`) nie liczy się do kryteriów wieku ani liczby dzieci — dopiero po urodzeniu.
Dzieci w sytuacji `loss` nie są brane pod uwagę.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, Field

from ..engine.derived import wymiar_macierzynskiego_tyg
from ..engine.kontrakt import load_kontrakt
from ..models.benefit import Benefit, Condition
from ..models.family import Child, FamilyView
from ..models.profile import Address, ParentProfile
from .units import units_for

MAJORITY_MONTHS = 18 * 12  # dziecko do ukończenia 18 lat

INSURANCE_LABELS = {"employment": "umowa o pracę", "mandate": "umowa zlecenia", "jdg": "działalność gospodarcza"}


class FamilyContext(BaseModel):
    children: list[Child]
    parents: list[ParentProfile]
    today: date
    address: Address
    answers: dict = Field(default_factory=dict)
    unit_ids: list[str] = Field(default_factory=list)  # jednostki obejmujące adres rodziny


class Question(BaseModel):
    condition_id: str
    text: str


class MatchResult(BaseModel):
    status: Literal["fits", "maybe", "no"]
    reasons: list[str] = Field(default_factory=list)
    unmet: list[str] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)
    # Dzieci, których dotyczy świadczenie `per_child` (puste dla świadczeń rodzinnych i przy `no`).
    child_ids: list[str] = Field(default_factory=list)


# ---------- pomocnicze ----------


def age_in_months(birth: date, today: date) -> int:
    """Pełne ukończone miesiące (31 stycznia -> 28 lutego to jeszcze 0 miesięcy)."""
    months = (today.year - birth.year) * 12 + today.month - birth.month
    if today.day < birth.day:
        months -= 1
    return max(months, 0)


def _plural(n: int, one: str, few: str, many: str) -> str:
    if n == 1:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def age_phrase(months: int) -> str:
    """„7 lat”, „2 lata”, „11 miesięcy” — poprawna polska odmiana."""
    if months < 24:
        return f"{months} {_plural(months, 'miesiąc', 'miesiące', 'miesięcy')}"
    years = months // 12
    return f"{years} {_plural(years, 'rok', 'lata', 'lat')}"


def _add_months(d: date, months: int) -> date:
    total = d.year * 12 + (d.month - 1) + months
    y, m = divmod(total, 12)
    return date(y, m + 1, min(d.day, calendar.monthrange(y, m + 1)[1]))


def _born(ctx: FamilyContext) -> list[Child]:
    return [c for c in ctx.children if c.status == "born" and c.birth_date and c.situation != "loss"]


def _expected(ctx: FamilyContext) -> list[Child]:
    return [c for c in ctx.children if c.status == "expected" and c.situation != "loss"]


def _has_ezla_b(ctx: FamilyContext) -> bool:
    return any(e.code.upper() == "B" and e.to_date >= ctx.today for p in ctx.parents for e in p.ezla)


def _pregnant(ctx: FamilyContext) -> bool:
    return bool(_expected(ctx)) or _has_ezla_b(ctx)


def _sickness_insured(ctx: FamilyContext) -> bool | None:
    """Czy któryś rodzic podlega ubezpieczeniu chorobowemu (prawo do zasiłków), według tytułów z ZUS.

    Umowa o pracę albo dobrowolne chorobowe przy zleceniu/działalności -> True. Zlecenie/działalność bez
    informacji o dobrowolnym chorobowym -> None (zapytamy). Brak jakiegokolwiek tytułu ubezpieczenia -> False.
    """
    unknown = False
    for p in ctx.parents:
        for ins in p.insurance:
            if ins.kind == "employment" or ins.voluntary_sickness is True:
                return True
            if ins.voluntary_sickness is None:
                unknown = True
    return None if unknown else False


def _no_maternity_allowance(ctx: FamilyContext) -> bool | None:
    """Czy rodzicom NIE przysługuje zasiłek macierzyński (odwrotność ubezpieczenia chorobowego)."""
    insured = _sickness_insured(ctx)
    return None if insured is None else not insured


def _all_parents_working(ctx: FamilyContext) -> bool | None:
    """Czy oboje rodzice pracują (mają tytuł ubezpieczenia). Gdy w aplikacji jest tylko jeden rodzic, nie wiemy,
    czy drugi pracuje albo czy rodzic wychowuje dziecko samodzielnie -> None (zapytamy)."""
    if len(ctx.parents) < 2:
        return None if all(p.insurance for p in ctx.parents) else False
    return all(p.insurance for p in ctx.parents)


def _born_together(child: Child, ctx: FamilyContext) -> int:
    return max(1, sum(1 for c in _born(ctx) if c.birth_date == child.birth_date))


def _in_maternity_leave(child: Child, ctx: FamilyContext) -> bool:
    """Czy od porodu nie minął jeszcze wymiar urlopu macierzyńskiego (Kodeks pracy art. 180, parametry silnika)."""
    weeks = wymiar_macierzynskiego_tyg(_born_together(child, ctx), load_kontrakt().params)
    return (ctx.today - child.birth_date).days < weeks * 7  # type: ignore[operator]


def _parental_window_open(child: Child, age: int, today: date) -> bool:
    """Do końca roku kalendarzowego, w którym dziecko kończy `age` lat (urlop rodzicielski: 6)."""
    return today <= date(child.birth_date.year + age, 12, 31)  # type: ignore[union-attr]


def _answer_key(benefit: Benefit, condition_id: str) -> str:
    return f"benefit:{benefit.id}:{condition_id}"


def _fact(ctx: FamilyContext, key: str) -> bool | None:
    """Wartość warunku `auto` z profilu rodziny; `None` = nie wiadomo."""
    if key == "family.pregnant":
        return _pregnant(ctx)
    if key == "family.has_ezla_b":
        return _has_ezla_b(ctx)
    if key == "family.child_serious_illness":
        return any(c.serious_illness for c in ctx.children if c.situation != "loss")
    if key == "family.no_maternity_allowance":
        return _no_maternity_allowance(ctx)
    if key == "family.sickness_insured":
        return _sickness_insured(ctx)
    if key == "family.all_parents_working":
        return _all_parents_working(ctx)
    value = ctx.answers.get(key)
    return value if isinstance(value, bool) else None


INCOME_PREFIX = "income_le:"


def income_answer_key(limit: float) -> str:
    """Odpowiedź „dochód na osobę nie przekracza `limit` zł” — wspólna dla świadczeń z tym samym progiem."""
    return f"{INCOME_PREFIX}{_fmt_zl(limit).replace(' ', '')}"


def _income_answer(ctx: FamilyContext, benefit: Benefit, limit: float) -> bool | None:
    """Odpowiedź o dochód: najpierw dla tego świadczenia, potem wywnioskowana z odpowiedzi przy innych progach.

    „Tak” przy niższym progu oznacza „tak” przy wyższym; „nie” przy wyższym oznacza „nie” przy niższym.
    """
    own = ctx.answers.get(_answer_key(benefit, "income"))
    if isinstance(own, bool):
        return own
    for key, value in ctx.answers.items():
        if not key.startswith(INCOME_PREFIX) or not isinstance(value, bool):
            continue
        other = _parse_money(key[len(INCOME_PREFIX):])
        if other is None:
            continue
        if value and other <= limit:
            return True
        if not value and other >= limit:
            return False
    return None


def _parse_money(value) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(str(value).replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def _fmt_zl(amount: float) -> str:
    return f"{amount:,.2f}".rstrip("0").rstrip(".").replace(",", " ") if amount % 1 else f"{int(amount):,}".replace(",", " ")


# ---------- kontekst ----------


def build_context(
    family_view: FamilyView,
    profiles: list[ParentProfile],
    today: date,
    units: list[dict] | None = None,
    viewer_id: str | None = None,
) -> FamilyContext:
    """Składa kontekst rodziny. Odpowiedzi rodziców są łączone; odpowiedzi `viewer_id` mają pierwszeństwo."""
    ordered = sorted(profiles, key=lambda p: p.user_id == viewer_id)  # viewer na końcu -> wygrywa
    answers: dict = {}
    for p in ordered:
        answers.update(p.answers)
    primary = next((p for p in profiles if p.user_id == viewer_id), profiles[0] if profiles else None)
    address = primary.address if primary else Address(city="", gmina="", powiat="", voivodeship="", postal_code="")
    return FamilyContext(
        children=list(family_view.children),
        parents=list(profiles),
        today=today,
        address=address,
        answers=answers,
        unit_ids=units_for(address, units or []) if primary else [],
    )


# ---------- dopasowanie ----------


def match_benefit(ctx: FamilyContext, benefit: Benefit) -> MatchResult:
    reasons: list[str] = []
    unmet: list[str] = []
    questions: list[Question] = []
    cr = benefit.criteria

    # --- zasięg terytorialny ---
    if benefit.scope != "national":
        if benefit.unit_id and benefit.unit_id in ctx.unit_ids:
            if benefit.scope == "municipal":
                reasons.append(f"mieszkasz w gminie {ctx.address.gmina}")
            else:
                reasons.append(f"mieszkasz w województwie ({ctx.address.voivodeship.lower()})")
        else:
            unmet.append("To świadczenie dotyczy mieszkańców innej gminy lub innego obszaru niż twój adres.")

    # --- wiek dziecka ---
    if cr.child_age_min_months is not None or cr.child_age_max_months is not None:
        lo = cr.child_age_min_months if cr.child_age_min_months is not None else 0
        hi = cr.child_age_max_months
        in_range = []
        for c in _born(ctx):
            months = age_in_months(c.birth_date, ctx.today)  # type: ignore[arg-type]
            if months >= lo and (hi is None or months <= hi):
                in_range.append((c, months))
        if in_range:
            reasons.extend(f"{c.name} ma {age_phrase(m)}" for c, m in in_range)
        else:
            if _expected(ctx) and not _born(ctx):
                unmet.append("Dostępne po urodzeniu dziecka. Dziecko w drodze liczy się dopiero po porodzie.")
            elif not _born(ctx):
                unmet.append("W rodzinie nie ma dzieci w wieku, którego dotyczy to świadczenie.")
            else:
                unmet.append(f"Żadne dziecko nie mieści się w wieku, w którym przysługuje to świadczenie ({_age_range_text(lo, hi)}).")
                if _expected(ctx):
                    unmet.append("Dziecko w drodze zostanie uwzględnione po urodzeniu.")

    # --- liczba dzieci ---
    if cr.min_children is not None:
        counted = [
            c
            for c in _born(ctx)
            if age_in_months(c.birth_date, ctx.today) < MAJORITY_MONTHS or c.has_disability  # type: ignore[arg-type]
        ]
        if len(counted) >= cr.min_children:
            reasons.append(f"macie {len(counted)} dzieci (wymagane co najmniej {cr.min_children})")
        else:
            msg = f"Potrzeba co najmniej {cr.min_children} dzieci, a w rodzinie jest {len(counted)}."
            if _expected(ctx) and len(counted) + len(_expected(ctx)) >= cr.min_children:
                msg += " Dziecko w drodze liczy się po urodzeniu."
            unmet.append(msg)

    # --- ciąża ---
    if cr.requires_pregnancy:
        if _pregnant(ctx):
            reasons.append("w rodzinie jest dziecko w drodze (ciąża)")
        else:
            unmet.append("To świadczenie jest dla osób w ciąży, a w rodzinie nie ma dziecka w drodze.")

    # --- ciąża albo noworodek ---
    if cr.pregnant_or_child_max_months is not None:
        hi = cr.pregnant_or_child_max_months
        newborns = [
            (c, age_in_months(c.birth_date, ctx.today))  # type: ignore[arg-type]
            for c in _born(ctx)
            if age_in_months(c.birth_date, ctx.today) <= hi  # type: ignore[arg-type]
        ]
        if _pregnant(ctx):
            reasons.append("w rodzinie jest dziecko w drodze (ciąża)")
        elif newborns:
            reasons.extend(f"{c.name} ma {age_phrase(m)}" for c, m in newborns)
        else:
            unmet.append(
                f"To świadczenie jest dla osób w ciąży lub z dzieckiem do {age_phrase(hi)}, a w rodzinie nie ma takiej sytuacji."
            )

    # --- ciąża albo dziecko do końca roku, w którym kończy N lat (urlop rodzicielski) ---
    if cr.pregnant_or_child_until_year_end_of_age is not None:
        age = cr.pregnant_or_child_until_year_end_of_age
        open_window = [c for c in _born(ctx) if _parental_window_open(c, age, ctx.today)]
        if _pregnant(ctx):
            reasons.append("w rodzinie jest dziecko w drodze (ciąża)")
        if open_window:
            reasons.extend(
                f"{c.name} ma {age_phrase(age_in_months(c.birth_date, ctx.today))}, "  # type: ignore[arg-type]
                f"a urlop można wykorzystać do końca {c.birth_date.year + age} roku"  # type: ignore[union-attr]
                for c in open_window
            )
        if not _pregnant(ctx) and not open_window:
            unmet.append(
                f"Ten urlop można wykorzystać do końca roku, w którym dziecko kończy {age} lat, "
                "a w rodzinie nie ma młodszego dziecka ani dziecka w drodze."
            )

    # --- ciąża albo trwa urlop macierzyński (wymiar zależy od liczby dzieci z porodu) ---
    if cr.pregnant_or_in_maternity_leave:
        on_leave = [c for c in _born(ctx) if _in_maternity_leave(c, ctx)]
        if _pregnant(ctx):
            reasons.append("w rodzinie jest dziecko w drodze (ciąża)")
        elif on_leave:
            reasons.extend(
                f"{c.name} ma {age_phrase(age_in_months(c.birth_date, ctx.today))}, więc urlop macierzyński jeszcze trwa"  # type: ignore[arg-type]
                for c in on_leave
            )
        else:
            unmet.append(
                "Urlop macierzyński trwa 20 tygodni od porodu (dłużej przy bliźniętach i kolejnych dzieciach z jednego "
                "porodu), a w rodzinie nie ma dziecka w drodze ani dziecka w tym okresie."
            )

    # --- niepełnosprawność / rodzina zastępcza ---
    live = [c for c in ctx.children if c.situation != "loss"]
    if cr.requires_disability:
        if any(c.has_disability for c in live):
            reasons.append("dziecko ma orzeczenie o niepełnosprawności")
        else:
            unmet.append(
                "W danych rodziny żadne dziecko nie ma zaznaczonej niepełnosprawności (możesz to zmienić w zakładce „Rodzina”)."
            )
    if cr.requires_foster:
        if any(c.foster for c in live):
            reasons.append("dziecko jest w rodzinie zastępczej")
        else:
            unmet.append("W danych rodziny nie ma dziecka w rodzinie zastępczej (możesz to zmienić w zakładce „Rodzina”).")

    # --- zatrudnienie ---
    if cr.employment_kinds:
        have = {i.kind for p in ctx.parents for i in p.insurance}
        matching = [k for k in cr.employment_kinds if k in have]
        if matching:
            reasons.append("w danych z ZUS widać: " + ", ".join(INSURANCE_LABELS[k] for k in matching))
        else:
            wanted = ", ".join(INSURANCE_LABELS[k] for k in cr.employment_kinds)
            unmet.append(f"W danych z ZUS nie widać wymaganego tytułu ubezpieczenia ({wanted}).")

    # --- dochód ---
    if cr.max_income_per_person is not None:
        limit = cr.max_income_per_person
        limit_txt = _fmt_zl(limit)
        known = _parse_money(ctx.answers.get("income_per_person"))
        answered = _income_answer(ctx, benefit, limit)
        if known is not None:
            if known <= limit:
                reasons.append(f"dochód na osobę ({_fmt_zl(known)} zł) nie przekracza {limit_txt} zł")
            else:
                unmet.append(f"Dochód na osobę ({_fmt_zl(known)} zł) przekracza próg {limit_txt} zł.")
        elif answered is True:
            reasons.append(f"dochód na osobę nie przekracza {limit_txt} zł")
        elif answered is False:
            unmet.append(f"Dochód na osobę przekracza próg {limit_txt} zł.")
        else:
            questions.append(
                Question(
                    condition_id="income",
                    text=f"Czy dochód na osobę w rodzinie nie przekracza {limit_txt} zł netto miesięcznie?",
                )
            )

    # --- warunki dodatkowe ---
    for cond in benefit.extra_conditions:
        _check_condition(ctx, benefit, cond, reasons, unmet, questions)

    child_ids: list[str] = []
    if benefit.per_child and not unmet:
        child_ids = [c.id for c in _concerned_children(ctx, benefit)]
        if not child_ids:
            unmet.append("Żadne dziecko nie spełnia wszystkich warunków tego świadczenia jednocześnie.")

    if unmet:
        return MatchResult(status="no", reasons=reasons, unmet=unmet, questions=[])
    if questions:
        return MatchResult(status="maybe", reasons=reasons, unmet=[], questions=questions, child_ids=child_ids)
    return MatchResult(status="fits", reasons=reasons, child_ids=child_ids)


def _concerned_children(ctx: FamilyContext, benefit: Benefit) -> list[Child]:
    """Dzieci, które jednocześnie spełniają kryteria „dziecięce” świadczenia (wiek, orzeczenie, ciężka choroba)."""
    cr = benefit.criteria
    born = _born(ctx)
    if cr.pregnant_or_child_max_months is not None:
        hi = cr.pregnant_or_child_max_months
        pool = [c for c in born if age_in_months(c.birth_date, ctx.today) <= hi]  # type: ignore[arg-type]
        if _pregnant(ctx):
            pool += _expected(ctx)
    elif cr.pregnant_or_child_until_year_end_of_age is not None:
        pool = [c for c in born if _parental_window_open(c, cr.pregnant_or_child_until_year_end_of_age, ctx.today)]
        if _pregnant(ctx):
            pool += _expected(ctx)
    elif cr.pregnant_or_in_maternity_leave:
        pool = [c for c in born if _in_maternity_leave(c, ctx)]
        if _pregnant(ctx):
            pool += _expected(ctx)
    else:
        pool = born
    if cr.child_age_min_months is not None or cr.child_age_max_months is not None:
        lo = cr.child_age_min_months or 0
        hi_age = cr.child_age_max_months
        pool = [
            c
            for c in pool
            if c.birth_date
            and age_in_months(c.birth_date, ctx.today) >= lo
            and (hi_age is None or age_in_months(c.birth_date, ctx.today) <= hi_age)
        ]
    if cr.requires_disability:
        pool = [c for c in pool if c.has_disability]
    if cr.requires_foster:
        pool = [c for c in pool if c.foster]
    if any(c.profile_key == "family.child_serious_illness" for c in benefit.extra_conditions):
        pool = [c for c in pool if c.serious_illness]
    return pool


def _check_condition(
    ctx: FamilyContext,
    benefit: Benefit,
    cond: Condition,
    reasons: list[str],
    unmet: list[str],
    questions: list[Question],
) -> None:
    value: bool | None = None
    if cond.kind == "auto" and cond.profile_key:
        value = _fact(ctx, cond.profile_key)
    if value is None:  # `ask` albo `auto`, którego nie da się sprawdzić po profilu
        stored = ctx.answers.get(_answer_key(benefit, cond.id))
        if isinstance(stored, bool):
            value = (not stored) if cond.negated_question else stored
    if value is True:
        reasons.append(cond.text[:1].lower() + cond.text[1:])
    elif value is False:
        unmet.append(cond.unmet_text or f"Warunek niespełniony: {cond.text}.")
    else:
        questions.append(Question(condition_id=cond.id, text=cond.question or cond.text))


def _age_range_text(lo: int, hi: int | None) -> str:
    if hi is None:
        return f"od {age_phrase(lo)}"
    if lo <= 0:
        return f"do {age_phrase(hi)} włącznie"
    return f"od {age_phrase(lo)} do {age_phrase(hi)} włącznie"


# ---------- terminy ----------


def next_deadline(benefit: Benefit, ctx: FamilyContext) -> date | None:
    """Najbliższy termin (nie wcześniejszy niż dziś) wyliczony z `benefit.deadline` względem dzieci rodziny."""
    d = benefit.deadline
    if d is None:
        return None
    candidates: list[date] = []
    if d.anchor == "fixed":
        if d.fixed_date:
            candidates.append(d.fixed_date)
    else:
        for c in ctx.children:
            if c.situation == "loss":
                continue
            if d.anchor == "due":
                base = c.due_date if c.status == "expected" else None
            elif d.anchor == "birth":
                base = c.birth_date if c.status == "born" else c.due_date
            else:  # child_age
                base = c.birth_date if c.status == "born" else None
            if base is None:
                continue
            when = _add_months(base, d.offset_months) if d.offset_months else base
            candidates.append(when + timedelta(days=d.offset_days or 0))
    upcoming = [x for x in candidates if x >= ctx.today]
    return min(upcoming) if upcoming else None
