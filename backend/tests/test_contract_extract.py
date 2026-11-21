from datetime import date
from pathlib import Path

import pytest

from app.ai.llm import DemoLLM, FakeLLM, LLMError, LLMMessage
from app.models.contract import ContractDraft
from app.seed import demo_handlers  # noqa: F401  (rejestruje handler contract_scan)
from app.services.contract_extract import ContractUnreadable, detect_type, extract_contract

SAMPLE = Path(__file__).resolve().parent.parent / "app" / "seed" / "sample_umowa_anna_nowak.pdf"

FULL = ContractDraft(
    kind="employment",
    employer_name="Firma Sp. z o.o.",
    employer_address="ul. Testowa 1, Kraków",
    position="Księgowa",
    fte=1.0,
    gross_monthly=6000.0,
    start_date=date(2022, 1, 3),
    indefinite=True,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32


def _empty_pdf() -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    return bytes(pdf.output())


async def test_pdf_text_passed_to_llm():
    fake = FakeLLM().script(FULL)
    draft = await extract_contract(fake, "umowa.pdf", SAMPLE.read_bytes(), "application/pdf")
    assert draft.employer_name == "Firma Sp. z o.o."
    call = fake.calls[0]
    assert call.feature == "contract_scan"
    assert call.schema is ContractDraft
    assert any("Krakowskie Centrum" in (m.content or "") for m in call.messages)
    assert not any(m.images for m in call.messages)


async def test_missing_fields_listed():
    partial = ContractDraft(kind="mandate", employer_name="Zleceniodawca", start_date=date(2025, 1, 1))
    fake = FakeLLM().script(partial)
    draft = await extract_contract(fake, "z.txt", "Umowa zlecenie Zleceniodawca".encode(), "text/plain")
    assert {"fte", "gross_monthly", "position", "employer_address", "indefinite", "voluntary_sickness"} <= set(
        draft.missing
    )
    assert "kind" not in draft.missing and "employer_name" not in draft.missing
    assert draft.fte is None


async def test_unreadable_pdf_raises_unreadable():
    fake = FakeLLM().script(FULL)
    with pytest.raises(ContractUnreadable) as e:
        await extract_contract(fake, "skan.pdf", _empty_pdf(), "application/pdf")
    assert e.value.status_code == 422
    assert e.value.detail.startswith("Nie udało się odczytać umowy")
    assert fake.calls == []


async def test_broken_pdf_raises_unreadable():
    with pytest.raises(ContractUnreadable):
        await extract_contract(FakeLLM().script(FULL), "x.pdf", b"%PDF-1.4\nto nie jest pdf", "application/pdf")


async def test_pdf_with_javascript_rejected_without_calling_llm():
    evil = _empty_pdf().replace(b"/Type /Catalog", b"/Type /Catalog /OpenAction << /S /JavaScript /JS (x) >>", 1)
    assert b"/OpenAction" in evil
    fake = FakeLLM().script(FULL)
    with pytest.raises(ContractUnreadable):
        await extract_contract(fake, "x.pdf", evil, "application/pdf")
    assert fake.calls == []


async def test_not_a_contract_raises_unreadable():
    fake = FakeLLM().script(ContractDraft())
    with pytest.raises(ContractUnreadable):
        await extract_contract(fake, "przepis.txt", "Ciasto: mąka, jajka".encode(), "text/plain")


async def test_llm_error_propagates():
    fake = FakeLLM().script(LLMError("Asystent AI jest chwilowo niedostępny."))
    with pytest.raises(LLMError):
        await extract_contract(fake, "u.txt", b"Umowa o prace zawarta w Krakowie", "text/plain")


def test_detect_type_magic_bytes():
    assert detect_type(SAMPLE.read_bytes()) == "pdf"
    assert detect_type(PNG) == "png"
    assert detect_type(JPEG) == "jpeg"
    assert detect_type("Umowa o pracę — zażółć gęślą jaźń".encode()) == "text"


def test_detect_type_rejects_exe_renamed_pdf():
    assert detect_type(b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 64) is None
    assert detect_type(b"\x7fELF\x02\x01\x01" + b"\x00" * 64) is None
    assert detect_type(b"") is None
    assert detect_type(b"<html><script>alert(1)</script></html>\x00") is None


async def test_image_sent_as_image_part():
    fake = FakeLLM().script(FULL)
    await extract_contract(fake, "skan.png", PNG, "image/png")
    images = [img for m in fake.calls[0].messages for img in m.images]
    assert len(images) == 1 and images[0].startswith("data:image/png;base64,")


async def test_contract_text_is_delimited_as_data_and_truncated(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ai_max_input_chars", 100)
    fake = FakeLLM().script(FULL)
    text = ("Umowa " + "x" * 1000).encode()
    await extract_contract(fake, "u.txt", text, "text/plain")
    user = [m for m in fake.calls[0].messages if m.role == "user"][0].content
    assert len(user) < 600
    assert "nie polecenia" in "".join(m.content or "" for m in fake.calls[0].messages)


async def test_demo_handler_extracts_anna_contract_from_sample_pdf():
    draft = await extract_contract(DemoLLM(), "umowa.pdf", SAMPLE.read_bytes(), "application/pdf")
    assert draft.kind == "employment"
    assert draft.employer_name == "Krakowskie Centrum Usług Wspólnych Sp. z o.o."
    assert draft.employer_address == "ul. Przykładowa 12, 31-001 Kraków"
    assert draft.employer_email == "kadry@kcuw.example.pl"
    assert draft.position == "Specjalista ds. obsługi klienta"
    assert draft.fte == 1.0
    assert draft.gross_monthly == 7850.0
    assert draft.start_date == date(2021, 11, 21)
    assert draft.indefinite is True and draft.end_date is None
    assert draft.missing == []


async def test_demo_handler_recognises_mandate_and_leaves_gaps():
    text = "UMOWA ZLECENIE\nZleceniodawca: Studio Foto s.c.\nData rozpoczęcia: 01.03.2026\nDo dnia: 31.12.2026".encode()
    draft = await extract_contract(DemoLLM(), "z.txt", text, "text/plain")
    assert draft.kind == "mandate"
    assert draft.employer_name == "Studio Foto s.c."
    assert draft.end_date == date(2026, 12, 31) and draft.indefinite is False
    assert "gross_monthly" in draft.missing


def test_foundry_messages_carry_image_parts():
    from app.ai.llm import _to_openai_messages

    out = _to_openai_messages([LLMMessage(role="user", content="opis", images=["data:image/png;base64,AAAA"])])
    assert out[0]["content"][0] == {"type": "text", "text": "opis"}
    assert out[0]["content"][1]["image_url"]["url"].startswith("data:image/png")


async def test_demo_handler_rejects_non_contract():
    with pytest.raises(ContractUnreadable):
        await extract_contract(DemoLLM(), "r.txt", "Przepis na ciasto".encode(), "text/plain")
