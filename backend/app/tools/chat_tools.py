"""Narzędzia czatu „Zapytaj mRodzinę” (plan 06): profil rodziny, przepisy, wyszukiwarka w sieci.

Zasady: narzędzia dostają `Principal` z kontekstu (z tokena), nigdy z argumentów modelu; profil nie zawiera
PESEL ani wysokości zarobków; wyniki są zwykłymi danymi (JSON) — opakowuje je pętla czatu.
"""

from __future__ import annotations

from ..ai.tools import ToolContext, ToolError, tool
from ..services.laws import load_default_index
from ..services.web_search import get_web_search, search_ranked

_MAX_LAW_TEXT = 1500


def _child_info(child: dict) -> dict:
    out: dict = {"name": child.get("name"), "status": child.get("status")}
    for key in ("birth_date", "due_date"):
        if child.get(key):
            out[key] = child[key]
    for key in ("has_disability", "foster", "serious_illness"):
        if child.get(key):
            out[key] = True
    if child.get("situation"):
        out["situation"] = child["situation"]
        out["situation_kind"] = child.get("situation_kind")
    return out


@tool(
    "profil_rodziny",
    "Zwraca dane rodziny zalogowanego rodzica: dzieci (imię, daty, sytuacja), rodziców (miasto, gmina, rodzaj "
    "ubezpieczenia, zwolnienia lekarskie) i odpowiedzi na pytania o uprawnienia. Bez PESEL i zarobków. "
    "Użyj, gdy odpowiedź zależy od sytuacji rodziny.",
    {"type": "object", "properties": {}, "additionalProperties": False},
)
async def profil_rodziny(ctx: ToolContext, args: dict) -> dict:
    family_id = ctx.principal.family_id
    if not family_id:
        return {"family": None, "note": "Rodzic nie utworzył jeszcze rodziny w aplikacji."}
    family = await ctx.store.get("families", family_id)
    if family is None:
        return {"family": None, "note": "Nie znaleziono rodziny."}
    children = await ctx.store.find("children", family_id=family_id)
    parents = []
    for uid in family.get("member_ids", []):
        profile = await ctx.store.get("profiles", uid)
        if profile is None:
            parents.append({"is_you": uid == ctx.principal.user_id, "profile": None})
            continue
        parents.append(
            {
                "first_name": profile.get("first_name"),
                "is_you": uid == ctx.principal.user_id,
                "city": profile["address"]["city"],
                "gmina": profile["address"]["gmina"],
                "voivodeship": profile["address"]["voivodeship"],
                "insurance": [
                    {"kind": i["kind"], "since": i["since"], "voluntary_sickness": i.get("voluntary_sickness")}
                    for i in profile.get("insurance", [])
                ],
                "sick_leave": [
                    {"code": e["code"], "from": e["from_date"], "to": e["to_date"]} for e in profile.get("ezla", [])
                ],
                "answers": profile.get("answers", {}),
            }
        )
    ordered = sorted(children, key=lambda c: (c.get("birth_date") or c.get("due_date") or "", c["id"]))
    return {
        "family": {"name": family.get("name")},
        "today": ctx.today.isoformat(),
        "parents": parents,
        "children": [_child_info(c) for c in ordered],
    }


@tool(
    "szukaj_w_przepisach",
    "Szuka w lokalnym indeksie przepisów (Kodeks pracy – uprawnienia rodzicielskie, ustawa zasiłkowa, ustawa o "
    "świadczeniach rodzinnych, 800+, Prawo oświatowe – rekrutacja, opieka nad dziećmi do lat 3, „Za życiem”, "
    "Karta Dużej Rodziny). Zwraca artykuły z linkiem do aktu. Cytuj artykuł i link w odpowiedzi.",
    {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "minLength": 2,
                "maxLength": 300,
                "description": "Pytanie lub słowa kluczowe po polsku.",
            },
            "k": {"type": "integer", "minimum": 1, "maximum": 8, "description": "Liczba artykułów (domyślnie 5)."},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)
async def szukaj_w_przepisach(ctx: ToolContext, args: dict) -> dict:
    results = load_default_index().search(args["query"], k=args.get("k", 5))
    return {
        "results": [
            {"act": c.act_short, "article": c.article, "text": c.text[:_MAX_LAW_TEXT], "url": c.url}
            for c in results
        ],
        "note": None if results else "Brak pasujących przepisów w indeksie.",
    }


@tool(
    "szukaj_w_sieci",
    "Wyszukuje informacje w sieci (preferuje strony urzędowe: gov.pl, BIP, ZUS, urzędy pracy, gminy). Użyj dla "
    "informacji lokalnych lub nowszych niż przepisy w indeksie. Podaj w odpowiedzi link do strony.",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 2, "maxLength": 300},
            "k": {"type": "integer", "minimum": 1, "maximum": 8},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)
async def szukaj_w_sieci(ctx: ToolContext, args: dict) -> dict:
    results = await search_ranked(get_web_search(), args["query"], args.get("k", 5))
    if not results:
        raise ToolError(
            "Wyszukiwarka internetowa jest niedostępna albo nic nie znalazła. "
            "Odpowiedz na podstawie przepisów albo wskaż, gdzie zapytać (urząd, ZUS, PUP)."
        )
    return {"results": [r.model_dump() for r in results]}
