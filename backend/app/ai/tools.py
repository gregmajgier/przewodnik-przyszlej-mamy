"""Rejestr narzędzi MCP (backend jest klientem MCP; narzędzia działają w procesie backendu).

Moduł `app/tools/<nazwa>.py` rejestruje narzędzia dekoratorem `@tool(...)`; `load_all_tools()`
importuje wszystkie moduły pakietu (poza zaczynającymi się od `_`). Nie edytuje się żadnego wspólnego pliku.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

import jsonschema

from ..security import Principal
from ..storage import Store
from .llm import ToolSpec

logger = logging.getLogger("mrodzina.ai.tools")

TOOLS_PACKAGE = "app.tools"


class ToolError(Exception):
    """Błąd narzędzia; komunikat (po polsku) może trafić do modelu, więc nie zawiera danych użytkownika."""


@dataclass
class ToolContext:
    principal: Principal
    store: Store
    today: date


@dataclass
class RegisteredTool:
    name: str
    description: str
    parameters: dict
    fn: Callable[[ToolContext, dict], Awaitable[Any]]


_REGISTRY: dict[str, RegisteredTool] = {}


def tool(name: str, description: str, parameters: dict) -> Callable:
    """Dekorator rejestrujący asynchroniczne narzędzie `async def fn(ctx: ToolContext, args: dict)`."""

    def decorator(fn: Callable[[ToolContext, dict], Awaitable[Any]]):
        if not inspect.iscoroutinefunction(fn):
            raise TypeError(f"Narzędzie {name!r} musi być funkcją async.")
        try:
            jsonschema.Draft202012Validator.check_schema(parameters)
        except jsonschema.SchemaError:
            raise ValueError(f"Narzędzie {name!r} ma niepoprawny schemat parametrów.") from None
        if name in _REGISTRY:
            raise ValueError(f"Narzędzie {name!r} jest już zarejestrowane.")
        _REGISTRY[name] = RegisteredTool(name, description, parameters, fn)
        return fn

    return decorator


def list_tools() -> list[ToolSpec]:
    return [ToolSpec(name=t.name, description=t.description, parameters=t.parameters) for t in _REGISTRY.values()]


async def call_tool(name: str, args: dict, ctx: ToolContext) -> Any:
    """Waliduje argumenty wg JSON Schema i wywołuje narzędzie. Zawsze rzuca tylko `ToolError`."""
    registered = _REGISTRY.get(name)
    if registered is None:
        raise ToolError(f"Nieznane narzędzie: {name}.")
    validator = jsonschema.Draft202012Validator(registered.parameters)
    errors = sorted(validator.iter_errors(args), key=lambda e: list(e.path))
    if errors:
        # bez wartości argumentów (mogą zawierać dane osobowe): tylko ścieżka i rodzaj reguły
        first = errors[0]
        where = first.json_path
        raise ToolError(f"Nieprawidłowe argumenty narzędzia {name}: pole {where} narusza regułę „{first.validator}”.")
    try:
        return await registered.fn(ctx, args)
    except ToolError:
        raise
    except Exception as e:  # noqa: BLE001 - treść wyjątku może zawierać dane; logujemy tylko typ
        logger.error("Narzędzie %s zakończyło się błędem: %s", name, type(e).__name__)
        raise ToolError(f"Narzędzie {name} nie mogło wykonać zapytania.") from None


def load_all_tools() -> None:
    """Importuje moduły pakietu `app.tools` (idempotentne; pomija moduły o nazwie zaczynającej się od `_`)."""
    package = importlib.import_module(TOOLS_PACKAGE)
    for info in pkgutil.iter_modules(package.__path__):
        if info.name.startswith("_"):
            continue
        importlib.import_module(f"{TOOLS_PACKAGE}.{info.name}")
