from datetime import date

import pytest

from app.ai import tools as reg
from app.ai.tools import ToolContext, ToolError, call_tool, list_tools, load_all_tools, tool
from app.security import Principal
from app.storage import MemoryStore


@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch):
    """Każdy test dostaje pusty rejestr (reszta aplikacji nie widzi narzędzi z testów)."""
    monkeypatch.setattr(reg, "_REGISTRY", {})


@pytest.fixture
def ctx():
    return ToolContext(
        principal=Principal("u1", "parent", "f1"), store=MemoryStore(), today=date(2026, 11, 21)
    )


SCHEMA = {
    "type": "object",
    "properties": {"n": {"type": "integer", "minimum": 0}},
    "required": ["n"],
    "additionalProperties": False,
}


def register_double():
    @tool("podwoj", "Podwaja liczbę", SCHEMA)
    async def podwoj(ctx: ToolContext, args: dict):
        return args["n"] * 2

    return podwoj


def test_register_and_list():
    register_double()
    specs = list_tools()
    assert [s.name for s in specs] == ["podwoj"]
    assert specs[0].description == "Podwaja liczbę"
    assert specs[0].parameters == SCHEMA


def test_duplicate_name_raises():
    register_double()
    with pytest.raises(ValueError):
        register_double()


async def test_call_returns_result(ctx):
    register_double()
    assert await call_tool("podwoj", {"n": 4}, ctx) == 8


async def test_call_validates_arguments(ctx):
    register_double()
    for bad in ({}, {"n": "x"}, {"n": -1}, {"n": 1, "extra": 2}):
        with pytest.raises(ToolError):
            await call_tool("podwoj", bad, ctx)


async def test_validation_error_does_not_echo_argument_values(ctx):
    register_double()
    with pytest.raises(ToolError) as e:
        await call_tool("podwoj", {"n": "PESEL-90010112345"}, ctx)
    assert "90010112345" not in str(e.value)


async def test_call_unknown_tool_raises_toolerror(ctx):
    with pytest.raises(ToolError):
        await call_tool("nie_ma", {}, ctx)


async def test_unexpected_exception_becomes_toolerror_without_leaking(ctx):
    @tool("psuje", "Zawsze pada", {"type": "object"})
    async def psuje(ctx: ToolContext, args: dict):
        raise RuntimeError("tajne dane rodziny")

    with pytest.raises(ToolError) as e:
        await call_tool("psuje", {}, ctx)
    assert "tajne" not in str(e.value)


async def test_toolerror_from_tool_passes_through(ctx):
    @tool("odmawia", "Odmawia", {"type": "object"})
    async def odmawia(ctx: ToolContext, args: dict):
        raise ToolError("Brak rodziny.")

    with pytest.raises(ToolError, match="Brak rodziny."):
        await call_tool("odmawia", {}, ctx)


async def test_tool_receives_context(ctx):
    seen = {}

    @tool("ctx", "Zapamiętuje kontekst", {"type": "object"})
    async def grab(c: ToolContext, args: dict):
        seen["c"] = c
        return "ok"

    await call_tool("ctx", {}, ctx)
    assert seen["c"] is ctx
    assert seen["c"].principal.user_id == "u1"


def test_sync_function_rejected():
    with pytest.raises(TypeError):

        @tool("sync", "Synchroniczna", {"type": "object"})
        def sync(ctx, args):
            return 1


def test_invalid_schema_rejected_at_registration():
    async def fn(c, a):
        return None

    with pytest.raises(ValueError):
        tool("zly", "Zły schemat", {"type": "no-such-type"})(fn)


def test_load_all_tools_idempotent():
    load_all_tools()
    first = [t.name for t in list_tools()]
    load_all_tools()
    assert [t.name for t in list_tools()] == first


def test_load_all_tools_imports_modules_but_skips_underscore(tmp_path, monkeypatch):
    import sys

    pkg = tmp_path / "fake_tools_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "alpha.py").write_text(
        "from app.ai.tools import tool\n"
        "@tool('alpha', 'A', {'type': 'object'})\n"
        "async def alpha(ctx, args):\n    return 1\n"
    )
    (pkg / "_hidden.py").write_text(
        "from app.ai.tools import tool\n"
        "@tool('hidden', 'H', {'type': 'object'})\n"
        "async def hidden(ctx, args):\n    return 1\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(reg, "TOOLS_PACKAGE", "fake_tools_pkg")
    load_all_tools()
    load_all_tools()
    names = [t.name for t in list_tools()]
    assert names == ["alpha"]
    for m in [m for m in sys.modules if m.startswith("fake_tools_pkg")]:
        del sys.modules[m]


async def test_example_tool_module_works(ctx):
    from app.tools._example import register_example

    register_example()
    assert await call_tool("echo", {"text": "hej"}, ctx) == {"text": "hej", "user_id": "u1"}
