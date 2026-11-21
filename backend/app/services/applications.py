"""Wnioski rodzica: tworzenie szkicu z prefillem, odpowiedzi na pytania, podgląd PDF, podpis i wysyłka.

Zasady (spec §8):
- Wnioskodawcą jest rodzic, który założył wniosek; drugi rodzic widzi go na liście rodziny, ale nie edytuje.
- Zawsze podgląd i zatwierdzenie przed wysyłką. Podpis (symulowany Profil Zaufany) obejmuje kanały PDF;
  zapisujemy odcisk danych z chwili podpisu — zmiana czegokolwiek unieważnia podpis.
- Wysyłka jest idempotentna po `application.id` (podwójne kliknięcie = jedna wiadomość).
- Dane wniosków (PESEL, PDF-y) nie trafiają do logów.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any

from ..errors import DomainError
from ..mail import MailProvider
from ..mail.sim_inbox import schedule_reply
from ..models.application import (
    FINAL_STATUSES,
    Application,
    ApplicationCreate,
    ApplicationPatch,
    Channel,
    MissingField,
)
from ..models.family import Child, FamilyView
from ..models.profile import ParentProfile
from ..storage import Store
from . import prefill as pf
from .employer_pdf import TITLES, EmployerData, render_employer_application
from .families import NO_FAMILY, FamilyService
from .pdf_fill import fill_pdf

logger = logging.getLogger("mrodzina.applications")

OPEN_STATUSES = ("draft", "needs_input", "ready")  # szkice, które można anulować
SIGNED_CHANNELS = ("employer_email", "pdf_download")

MSG_FINAL = "Ten wniosek został już złożony i nie można go zmieniać."
MSG_LOSS = "Dla tego dziecka nie składamy już wniosków. Jeśli to pomyłka, zmień dane dziecka w zakładce „Rodzina”."


# ---------- katalog i kanały ----------


def loss_forms() -> frozenset[str]:
    """Formularze z świadczeń wsparcia po stracie (np. zasiłek macierzyński po martwym urodzeniu): wolno je
    złożyć także o dziecko w sytuacji straty."""
    from ..seed.benefits import load_loss_benefits

    return frozenset(code for b in load_loss_benefits() for code in b.form_codes)


def _catalog() -> dict[str, dict]:
    return {w["kod"]: w for w in pf._read_json(pf.DATA / "katalog_wnioskow_pdf.json")["wnioski"]}


def channels_for(code: str) -> list[Channel]:
    """Dostępne kanały: pracodawca → e-mail z PDF; ZUS/gmina → agent w makiecie i/lub PDF; wnioski tylko
    elektroniczne (800+, Aktywny rodzic) → wyłącznie agent."""
    entry = _catalog().get(code)
    if code in pf.EMPLOYER_KINDS:
        return ["employer_email", "pdf_download"]
    if entry is None or entry.get("rola"):
        return []
    channels: list[Channel] = []
    if code in pf.CODE_TO_PORTAL:
        channels.append("portal_agent")
    mapping = pf.load_map(code)
    if mapping and mapping.get("pdf") and mapping.get("fields") and not entry.get("tylko_elektronicznie"):
        channels.append("pdf_download")
    return channels


def supported_codes() -> list[str]:
    codes = [c for c in _catalog() if channels_for(c)]
    codes += [c for c in pf.EMPLOYER_KINDS if c not in codes]
    return codes


def _digest(app: Application, values: dict[str, Any]) -> str:
    payload = {"form": app.form_code, "channel": app.channel, "to": app.recipient_email, "values": values}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------- blokady (idempotencja wysyłki) ----------

_locks: dict[tuple[int, str], asyncio.Lock] = {}


def _lock_for(app_id: str) -> asyncio.Lock:
    """Blokada na wniosek (per pętla zdarzeń): dwa równoległe `submit` tego samego wniosku wysyłają raz."""
    key = (id(asyncio.get_running_loop()), app_id)
    return _locks.setdefault(key, asyncio.Lock())


def _drop_lock(app_id: str) -> None:
    _locks.pop((id(asyncio.get_running_loop()), app_id), None)


# ---------- anulowanie szkiców (plan 10: tryb straty) ----------


async def list_family_applications(store: Store, family_id: str) -> list[Application]:
    """Wszystkie wnioski rodziny, od najstarszego."""
    apps = [Application.model_validate(d) for d in await store.find("applications", family_id=family_id)]
    apps.sort(key=lambda a: (a.created_at, a.id))
    return apps


async def cancel_drafts_for_child(store: Store, child_id: str) -> int:
    """Anuluje niewysłane wnioski dotyczące dziecka; zwraca liczbę anulowanych."""
    count = 0
    for doc in await store.find("applications", child_id=child_id):
        if doc.get("status") in OPEN_STATUSES:
            await store.put("applications", {**doc, "status": "cancelled", "signed_at": None, "signed_digest": None})
            count += 1
    return count


class ApplicationService:
    def __init__(self, store: Store, mail: MailProvider | None = None) -> None:
        self.store = store
        self.mail = mail

    # ---------- kontekst ----------

    async def _family_id(self, user_id: str) -> str:
        user = await self.store.get("users", user_id)
        family_id = user.get("family_id") if user else None
        if not family_id:
            raise DomainError(404, NO_FAMILY)
        return family_id

    async def _context(self, user_id: str) -> tuple[FamilyView, list[ParentProfile]]:
        view = await FamilyService(self.store).get_family_view(user_id)
        profiles: list[ParentProfile] = []
        for member_id in view.family.member_ids:
            doc = await self.store.get("profiles", member_id)
            if doc is not None:
                profiles.append(ParentProfile.model_validate({**doc, "user_id": member_id}))
        if not profiles:
            raise DomainError(404, "Nie znaleziono profilu. Zaloguj się ponownie przez mObywatela.")
        return view, profiles

    async def _own(self, user_id: str, app_id: str, *, mutate: bool = False) -> Application:
        """Wniosek rodziny zalogowanego rodzica; cudzy lub nieistniejący → 404 (bez zdradzania istnienia)."""
        family_id = await self._family_id(user_id)
        doc = await self.store.get("applications", app_id)
        if doc is None or doc.get("family_id") != family_id:
            raise DomainError(404, "Nie znaleziono takiego wniosku.")
        app = Application.model_validate(doc)
        if mutate and app.applicant_id != user_id:
            raise DomainError(403, "Ten wniosek składa drugi rodzic. Możesz go tylko przeglądać.")
        return app

    async def _save(self, app: Application) -> Application:
        await self.store.put("applications", app.model_dump(mode="json"))
        return app

    # ---------- przeliczanie ----------

    def _refresh(self, app: Application, view: FamilyView, profiles: list[ParentProfile]) -> Application:
        """Przelicza wartości i brakujące dane; ustawia status (poza statusami końcowymi)."""
        if app.status in FINAL_STATUSES:
            return app
        fields = pf.form_schema(app.form_code)
        result = pf.prefill_fields(fields, view, profiles, app.child_id, app.answers, app.applicant_id)
        missing = [MissingField(**q.model_dump()) for q in result.missing]
        values = dict(result.values)

        email = values.get("employer_email")
        if isinstance(email, str) and not pf._EMAIL_RE.fullmatch(email):
            email = None
            values.pop("employer_email", None)
        app.recipient_email = email if app.channel == "employer_email" else None
        app.recipient_domain = email.rsplit("@", 1)[1] if app.recipient_email else None
        if app.channel == "employer_email" and not email and all(m.field_id != "employer_email" for m in missing):
            label = next((f.label for f in fields if f.id == "employer_email"), "Adres e-mail pracodawcy")
            missing.append(MissingField(field_id="employer_email", label=label, type="text"))

        app.values, app.missing = values, missing
        if missing:
            app.status, app.signed_at, app.signed_digest = "needs_input", None, None
        elif app.signed_at and app.signed_digest == _digest(app, values):
            app.status = "ready"
        else:
            app.status, app.signed_at, app.signed_digest = "draft", None, None
        return app

    @staticmethod
    def _child(view: FamilyView, child_id: str | None) -> Child | None:
        return next((c for c in view.children if c.id == child_id), None) if child_id else None

    async def _guard_loss(self, app: Application, view: FamilyView) -> None:
        child = self._child(view, app.child_id)
        if child is not None and child.situation == "loss" and app.form_code not in loss_forms():
            await cancel_drafts_for_child(self.store, child.id)
            raise DomainError(409, MSG_LOSS)

    # ---------- katalog ----------

    async def forms(self, user_id: str) -> dict:
        _, profiles = await self._context(user_id)
        me = next((p for p in profiles if p.user_id == user_id), profiles[0])
        kind = me.insurance[0].kind if me.insurance else None
        catalog = _catalog()
        items = []
        for code in supported_codes():
            channels = channels_for(code)
            entry = catalog.get(code, {})
            items.append(
                {
                    "code": code,
                    "name": entry.get("nazwa") or TITLES.get(code, code),
                    "institution": entry.get("instytucja"),
                    "deadline": entry.get("termin"),
                    "channels": channels,
                    "default_channel": channels[0],
                    "only_electronic": bool(entry.get("tylko_elektronicznie")),
                    "requires_child": pf.requires_child(code),
                    "loss_ok": code in loss_forms(),
                    "portal_id": pf.CODE_TO_PORTAL.get(code),
                }
            )
        return {"forms": items, "recommended_flow": pf.recommend_flow(kind)}

    # ---------- CRUD ----------

    async def create(self, user_id: str, data: ApplicationCreate) -> Application:
        allowed = channels_for(data.form_code)
        if not allowed:
            raise DomainError(422, "Dla tego wniosku nie ma jeszcze kreatora w aplikacji.")
        channel = data.channel or allowed[0]
        if channel not in allowed:
            raise DomainError(422, self._channel_error(data.form_code, channel))
        if pf.requires_child(data.form_code) and not data.child_id:
            raise DomainError(422, "Wybierz dziecko, którego dotyczy wniosek.")

        view, profiles = await self._context(user_id)
        child = pf._select_child(view, data.child_id)  # cudze/nieistniejące dziecko → 404
        if child is not None and child.situation == "loss" and data.form_code not in loss_forms():
            raise DomainError(409, MSG_LOSS)
        app = Application(
            id=f"app-{uuid.uuid4().hex[:12]}",
            family_id=view.family.id,
            applicant_id=user_id,
            form_code=data.form_code,
            child_id=child.id if child else None,
            channel=channel,
            created_at=_now(),
        )
        return await self._save(self._refresh(app, view, profiles))

    @staticmethod
    def _channel_error(code: str, channel: str) -> str:
        if _catalog().get(code, {}).get("tylko_elektronicznie") and channel == "pdf_download":
            return "Ten wniosek można złożyć tylko elektronicznie — wersja PDF nie jest dostępna."
        return "Ten wniosek nie obsługuje wybranego sposobu złożenia."

    async def list_for_family(self, user_id: str) -> list[Application]:
        family_id = await self._family_id(user_id)
        docs = await self.store.find("applications", family_id=family_id)
        return sorted((Application.model_validate(d) for d in docs), key=lambda a: a.created_at, reverse=True)

    async def get(self, user_id: str, app_id: str) -> Application:
        app = await self._own(user_id, app_id)
        if app.status in FINAL_STATUSES:
            return app
        view, profiles = await self._context(user_id)
        return await self._save(self._refresh(app, view, profiles))

    def _field_map(self, app: Application) -> dict[str, pf.FormField]:
        return {f.id: f for f in pf.form_schema(app.form_code)}

    async def patch(self, user_id: str, app_id: str, patch: ApplicationPatch) -> Application:
        app = await self._own(user_id, app_id, mutate=True)
        if app.status in FINAL_STATUSES:
            raise DomainError(409, MSG_FINAL)
        if patch.channel is not None and patch.channel != app.channel:
            if patch.channel not in channels_for(app.form_code):
                raise DomainError(422, self._channel_error(app.form_code, patch.channel))
            app.channel = patch.channel
        if patch.values:
            fields = self._field_map(app)
            answers = dict(app.answers)
            for field_id, value in patch.values.items():
                field = fields.get(field_id)
                if field is None:
                    raise DomainError(422, "Ten wniosek nie ma takiego pola.")
                if value is None:
                    answers.pop(field_id, None)  # powrót do wartości z profilu
                else:
                    answers[field_id] = pf.validate_answer(field, value)
            app.answers = answers
        view, profiles = await self._context(user_id)
        return await self._save(self._refresh(app, view, profiles))

    async def answer(self, user_id: str, app_id: str, answers: dict[str, Any]) -> Application:
        """Odpowiedzi na pytania o brakujące dane. Zapamiętujemy je w profilu (nie pytamy drugi raz)."""
        app = await self._own(user_id, app_id, mutate=True)
        if app.status in FINAL_STATUSES:
            raise DomainError(409, MSG_FINAL)
        if not answers:
            raise DomainError(422, "Podaj odpowiedź.")
        fields = self._field_map(app)
        clean: dict[str, Any] = {}
        for field_id, value in answers.items():
            field = fields.get(field_id)
            if field is None:
                raise DomainError(422, "Ten wniosek nie ma takiego pola.")
            clean[field_id] = pf.validate_answer(field, value)
        app.answers = {**app.answers, **clean}
        await self._remember(user_id, app, fields, clean)
        view, profiles = await self._context(user_id)
        return await self._save(self._refresh(app, view, profiles))

    async def _remember(
        self, user_id: str, app: Application, fields: dict[str, pf.FormField], clean: dict[str, Any]
    ) -> None:
        profile_updates: dict[str, bool | str] = {}
        for field_id, value in clean.items():
            source = fields[field_id].source_key or ""
            if source.startswith("answers.") and isinstance(value, (bool, str)):
                profile_updates[source.partition(".")[2]] = value
            elif source == "child.pesel" and app.child_id and isinstance(value, str):
                child_doc = await self.store.get("children", app.child_id)
                if child_doc is not None and child_doc.get("family_id") == app.family_id:
                    await self.store.put("children", {**child_doc, "pesel": value})
        if profile_updates:
            doc = await self.store.get("profiles", user_id)
            if doc is not None:
                answers = {**doc.get("answers", {}), **profile_updates}
                await self.store.put("profiles", {**doc, "answers": answers, "id": user_id})

    # ---------- PDF ----------

    async def _complete(self, user_id: str, app_id: str, *, mutate: bool) -> tuple[Application, FamilyView, ParentProfile]:
        app = await self._own(user_id, app_id, mutate=mutate)
        view, profiles = await self._context(user_id)
        await self._guard_loss(app, view)
        app = self._refresh(app, view, profiles)
        applicant = next((p for p in profiles if p.user_id == app.applicant_id), profiles[0])
        return app, view, applicant

    def _render(self, app: Application, view: FamilyView, applicant: ParentProfile) -> bytes:
        code, values = app.form_code, app.values
        if code in pf.EMPLOYER_KINDS:
            child = self._child(view, app.child_id)
            weeks = str(values.get("parental_weeks", "")).strip()
            try:
                data = EmployerData(
                    first_name=values["first_name"],
                    last_name=values["last_name"],
                    employer_name=values["employer_name"],
                    child_name=values["child_name"],
                    child_date=date.fromisoformat(values["child_date"]),
                    child_born=bool(child and child.status == "born"),
                    leave_start=date.fromisoformat(values["leave_start"]) if values.get("leave_start") else None,
                    leave_end=date.fromisoformat(values["leave_end"]) if values.get("leave_end") else None,
                    parental_weeks=int(weeks) if weeks.isdigit() else None,
                    city=applicant.address.city or None,
                    applicant_address=f"{applicant.address.postal_code} {applicant.address.city}".strip() or None,
                )
            except (KeyError, ValueError):
                raise DomainError(422, "Dane wniosku są niepoprawne. Sprawdź daty i uzupełnij pola.") from None
            return render_employer_application(code, data)
        if pf.load_map(code) and pf.load_map(code).get("pdf"):
            return fill_pdf(code, values)
        raise DomainError(422, "Ten wniosek składasz przez portal — nie ma dla niego wersji PDF.")

    async def pdf(self, user_id: str, app_id: str) -> tuple[str, bytes]:
        """Podgląd PDF: (kod formularza, bajty). Wymaga kompletu danych."""
        app, view, applicant = await self._complete(user_id, app_id, mutate=False)
        if app.missing:
            raise DomainError(409, "Uzupełnij brakujące dane, żeby zobaczyć podgląd.")
        return app.form_code, self._render(app, view, applicant)

    # ---------- podpis i wysyłka ----------

    async def sign(self, user_id: str, app_id: str) -> Application:
        """Symulowany podpis Profilem Zaufanym (modal w aplikacji) — warunek wysyłki kanałów PDF."""
        app, _, _ = await self._complete(user_id, app_id, mutate=True)
        if app.status in FINAL_STATUSES:
            raise DomainError(409, MSG_FINAL)
        if app.channel not in SIGNED_CHANNELS:
            raise DomainError(409, "Ten wniosek składasz przez portal — podpisujesz go w makiecie portalu.")
        if app.status == "needs_input":
            raise DomainError(409, "Uzupełnij brakujące dane przed podpisaniem.")
        app.signed_at = _now()
        app.signed_digest = _digest(app, app.values)
        app.status = "ready"
        return await self._save(app)

    async def submit(self, user_id: str, app_id: str) -> Application:
        """Wysyła wniosek (e-mail do pracodawcy z PDF albo oznacza złożenie PDF). Idempotentne po `id`."""
        lock = _lock_for(app_id)
        try:
            async with lock:
                return await self._submit_locked(user_id, app_id)
        finally:
            if not lock.locked():
                _drop_lock(app_id)

    async def _submit_locked(self, user_id: str, app_id: str) -> Application:
        app = await self._own(user_id, app_id, mutate=True)
        if app.status in FINAL_STATUSES - {"cancelled"}:
            return app  # już wysłany — nie wysyłamy drugi raz
        if app.status == "cancelled":
            raise DomainError(409, "Ten wniosek został anulowany.")
        if app.channel == "portal_agent":
            raise DomainError(409, "Ten wniosek wysyła agent w makiecie portalu.")
        was_signed = app.signed_at is not None
        app, view, applicant = await self._complete(user_id, app_id, mutate=True)
        if app.status == "needs_input":
            await self._save(app)
            raise DomainError(409, "Brakuje danych we wniosku. Uzupełnij je przed wysłaniem.")
        if app.status != "ready":
            await self._save(app)
            if was_signed:
                raise DomainError(409, "Dane wniosku zmieniły się po podpisaniu. Sprawdź podgląd i podpisz ponownie.")
            raise DomainError(409, "Najpierw zatwierdź i podpisz wniosek.")

        if app.channel == "employer_email":
            if self.mail is None or not app.recipient_email:
                raise DomainError(409, "Podaj adres e-mail pracodawcy.")
            pdf = self._render(app, view, applicant)
            name = f"{app.form_code}.pdf"
            who = f"{app.values.get('first_name', '')} {app.values.get('last_name', '')}".strip()
            try:
                sent = await self.mail.send(
                    app.family_id,
                    user_id,
                    app.recipient_email,
                    TITLES.get(app.form_code, "Wniosek"),
                    "Dzień dobry,\n\nw załączeniu przesyłam wniosek w formie PDF. "
                    "Proszę o potwierdzenie jego otrzymania.\n\n"
                    f"Z poważaniem\n{who}",
                    [(name, pdf)],
                )
            except Exception as e:  # noqa: BLE001 — treść wiadomości i PDF nie trafiają do logów
                logger.error("Nie wysłano wniosku %s: %s", app.id, type(e).__name__)
                raise DomainError(502, "Nie udało się wysłać wiadomości. Spróbuj ponownie za chwilę.") from None
            app.thread_id = sent.thread_id
        app.status, app.sent_at = "sent", _now()
        app = await self._save(app)
        if app.channel == "employer_email":
            await schedule_reply(self.store, app, app.sent_at)  # symulowana odpowiedź pracodawcy (plan 09)
        return app

    async def portal_submitted(self, user_id: str, app_id: str) -> Application:
        """Callback makiety portalu: rodzic zatwierdził i „wysłał” wniosek w makiecie. Idempotentne."""
        lock = _lock_for(app_id)
        try:
            async with lock:
                app = await self._own(user_id, app_id, mutate=True)
                if app.channel != "portal_agent":
                    raise DomainError(409, "Ten wniosek nie jest składany przez portal.")
                if app.status in FINAL_STATUSES - {"cancelled"}:
                    return app
                if app.status == "cancelled":
                    raise DomainError(409, "Ten wniosek został anulowany.")
                app, _, _ = await self._complete(user_id, app_id, mutate=True)
                if app.status == "needs_input":
                    await self._save(app)
                    raise DomainError(409, "Brakuje danych we wniosku. Uzupełnij je przed wysłaniem.")
                app.status, app.sent_at = "sent", _now()
                # makieta portalu = adresat do filtra poczty: ZUS (eZUS) albo urząd gminy (Emp@tia)
                zus = (pf.CODE_TO_PORTAL.get(app.form_code) or "").startswith("ezus")
                app.recipient_email = "wnioski@zus.pl" if zus else "swiadczenia@um.krakow.pl"
                app.recipient_domain = app.recipient_email.rsplit("@", 1)[1]
                app = await self._save(app)
                await schedule_reply(self.store, app, app.sent_at)  # symulowana odpowiedź urzędu (plan 09)
                return app
        finally:
            if not lock.locked():
                _drop_lock(app_id)

    # ---------- agent ----------

    async def portal_context(self, user_id: str, app_id: str) -> tuple[Application, pf.PrefillResult, str]:
        """Dane do planu agenta: wniosek (świeżo przeliczony), wynik prefillu portalu i id makiety."""
        app, _, _ = await self._complete(user_id, app_id, mutate=True)
        if app.status in FINAL_STATUSES:
            raise DomainError(409, MSG_FINAL)
        portal_id = pf.CODE_TO_PORTAL.get(app.form_code)
        if app.channel != "portal_agent" or portal_id is None:
            raise DomainError(409, "Ten wniosek nie jest składany przez portal.")
        # schemat portalu = schemat wniosku (`form_schema` korzysta z tych samych pól), więc prefill już policzony
        result = pf.PrefillResult(
            values=dict(app.values), missing=[pf.Question(**m.model_dump()) for m in app.missing]
        )
        return await self._save(app), result, portal_id
