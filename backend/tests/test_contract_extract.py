import asyncio
from datetime import date
from pathlib import Path

import pytest

from app.ai.llm import DemoLLM, FakeLLM, LLMError
from app.models.contract import ContractDraft
from app.seed import demo_handlers  # noqa: F401 - rejestruje handler demo
from app.services.contract_extract import (
    ContractUnreadable,
    ExtractionResult,
    detect_type,
    extract_contract,
)

SAMPLE = Path(__file__).resolve().parent.parent / "app" / "seed" / "sample_umowa_anna_nowak.pdf"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
TEXT = (
    "UMOWA O PRACĘ\nPracodawca: Firma Testowa Sp. z o.o.\nAdres pracodawcy: ul. Długa 1, Kraków\n"
    "Stanowisko: Księgowa\nWymiar etatu: pełny etat\nWynagrodzenie: 6000,00 zł brutto\n"
    "Data rozpoczęcia pracy: 01.02.2024\nOkres zatrudnienia: na czas określony do 31.12.2026\n"
).encode()


def run(coro):
    return asyncio.run(coro)


def full_draft(**kw) -> ContractDraft:
    base = dict(
        kind="employment",
        employer_name="Firma",
        employer_address="Kraków",
        position="Księgowa",
        fte=1.0,
        gross_monthly=6000,
        start_date=date(2024, 2, 1),
        indefinite=True,
    )
    return ContractDraft(**{**base, **kw})


def test_pdf_text_passed_to_llm():
    fake = FakeLLM().script(full_draft())
    draft = run(extract_contract(fake, "umowa.pdf", SAMPLE.read_bytes(), "application/pdf"))
    assert draft.missing == []
    call = fake.calls[0]
    assert call.feature == "contract_scan"
    user = call.messages[-1]
    assert "Krakowskie Centrum Usług Wspólnych" in user.content
    assert not user.images


def test_missing_fields_listed():
    fake = FakeLLM().script(ContractDraft(kind="employment", employer_name="Firma", start_date=date(2024, 1, 1)))
    draft = run(extract_contract(fake, "u.txt", TEXT, "text/plain"))
    assert draft.employer_address is None
    assert set(draft.missing) == {"employer_address", "position", "gross_monthly", "fte", "indefinite"}


def test_missing_ignores_model_supplied_list_and_flags_end_date():
    fake = FakeLLM().script(full_draft(indefinite=False, end_date=None, missing=["nonsense"]))
    draft = run(extract_contract(fake, "u.txt", TEXT, "text/plain"))
    assert draft.missing == ["end_date"]


def test_mandate_requires_voluntary_sickness_answer():
    fake = FakeLLM().script(full_draft(kind="mandate", fte=None, voluntary_sickness=None))
    draft = run(extract_contract(fake, "u.txt", TEXT, "text/plain"))
    assert draft.missing == ["voluntary_sickness"]


def test_unreadable_pdf_raises_unreadable():
    fake = FakeLLM()
    with pytest.raises(ContractUnreadable) as e:
        run(extract_contract(fake, "u.pdf", b"%PDF-1.4\ngarbage without structure", "application/pdf"))
    assert e.value.status_code == 422
    assert "Nie udało się odczytać umowy" in e.value.detail
    assert fake.calls == []


def test_pdf_without_text_layer_unreadable():
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    with pytest.raises(ContractUnreadable):
        run(extract_contract(FakeLLM(), "skan.pdf", bytes(pdf.output()), "application/pdf"))


def test_pdf_with_javascript_rejected():
    content = SAMPLE.read_bytes().replace(b"%PDF-1.3", b"%PDF-1.3\n% /JavaScript", 1)
    content = content if b"/JavaScript" in content else content + b"\n/JavaScript"
    with pytest.raises(ContractUnreadable) as e:
        run(extract_contract(FakeLLM(), "u.pdf", content, "application/pdf"))
    assert "skrypty" in e.value.detail


def test_detect_type_rejects_exe_renamed_pdf():
    exe = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff" + b"\x00" * 100
    assert detect_type(exe) is None
    with pytest.raises(ContractUnreadable):
        run(extract_contract(FakeLLM(), "umowa.pdf", exe, "application/pdf"))


def test_detect_type_basic():
    assert detect_type(SAMPLE.read_bytes()) == "pdf"
    assert detect_type(PNG) == "png"
    assert detect_type(b"\xff\xd8\xff\xe0" + b"\x00" * 10) == "jpeg"
    assert detect_type(TEXT) == "text"
    assert detect_type(b"   ") is None


def test_declared_type_mismatch_rejected():
    with pytest.raises(ContractUnreadable):
        run(extract_contract(FakeLLM(), "a.png", TEXT, "image/png"))


def test_image_sent_as_image_part():
    fake = FakeLLM().script(full_draft())
    run(extract_contract(fake, "foto.png", PNG, "image/png"))
    user = fake.calls[0].messages[-1]
    assert len(user.images) == 1 and user.images[0].startswith("data:image/png;base64,")


def test_not_a_contract_rejected():
    fake = FakeLLM().script(ExtractionResult(is_contract=False))
    with pytest.raises(ContractUnreadable):
        run(extract_contract(fake, "u.txt", TEXT, "text/plain"))


def test_llm_error_maps_to_unreadable():
    fake = FakeLLM().script(LLMError("x"))
    with pytest.raises(ContractUnreadable):
        run(extract_contract(fake, "u.txt", TEXT, "text/plain"))


def test_demo_handler_extracts_anna_contract_from_sample_pdf():
    draft = run(extract_contract(DemoLLM(), "umowa.pdf", SAMPLE.read_bytes(), "application/pdf"))
    assert draft.kind == "employment"
    assert draft.employer_name == "Krakowskie Centrum Usług Wspólnych Sp. z o.o."
    assert draft.employer_email == "kadry@kcuw.example.pl"
    assert draft.position == "Specjalista ds. obsługi klienta"
    assert draft.fte == 1.0
    assert draft.gross_monthly == 7850.0
    assert draft.start_date == date(2021, 11, 21)
    assert draft.indefinite is True and draft.end_date is None
    assert draft.missing == []


def test_demo_handler_fixed_term_text():
    draft = run(extract_contract(DemoLLM(), "u.txt", TEXT, "text/plain"))
    assert draft.indefinite is False and draft.end_date == date(2026, 12, 31)
