from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..errors import DomainError
from ..security import Principal, require_official
from ..services.national_parameters import apply_overrides, flatten_leaves
from ..storage import Store, get_store

router = APIRouter(prefix="/api/official/national-parameters", tags=["national-parameters"])
DATA = Path(__file__).resolve().parents[1] / "data"
DOCUMENT_ID = "national-active"


class ParametersIn(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict, max_length=300)


def _rules() -> dict:
    return json.loads((DATA / "reguly_uprawnien.json").read_text(encoding="utf-8"))


@router.get("")
async def get_parameters(p: Principal = Depends(require_official), store: Store = Depends(get_store)) -> dict:
    rules = _rules()
    base_tree = rules["parametry_drzewo"]
    doc = await store.get("engine_parameters", DOCUMENT_ID)
    overrides = doc.get("overrides", {}) if doc else {}
    active = apply_overrides(base_tree, overrides)
    return {
        "base": flatten_leaves(base_tree),
        "active": flatten_leaves(active),
        "overrides": overrides,
        "updated_at": doc.get("updated_at") if doc else None,
        "version": rules["meta"]["wersja"],
        "simulation": True,
    }


@router.put("")
async def update_parameters(
    body: ParametersIn, p: Principal = Depends(require_official), store: Store = Depends(get_store)
) -> dict:
    rules = _rules()
    base_tree = rules["parametry_drzewo"]
    base_paths = {row["path"]: row["value"] for row in flatten_leaves(base_tree)}
    clean: dict[str, Any] = {}
    for path, value in body.values.items():
        if path not in base_paths:
            raise DomainError(422, f"Nieznana ścieżka parametru: {path}")
        base_type = type(base_paths[path])
        if base_type is bool:
            if not isinstance(value, bool):
                raise DomainError(422, f"Parametr {path} musi być wartością tak/nie.")
            clean[path] = value
        elif base_type in (int, float):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise DomainError(422, f"Parametr {path} musi być liczbą.")
            if value < 0:
                raise DomainError(422, f"Parametr {path} nie może być ujemny.")
            clean[path] = value
        elif base_type is str:
            if not isinstance(value, str):
                raise DomainError(422, f"Parametr {path} musi być tekstem.")
            clean[path] = value
    doc = {
        "id": DOCUMENT_ID,
        "overrides": clean,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": p.user_id,
    }
    await store.put("engine_parameters", doc)
    return await get_parameters(p=p, store=store)


@router.post("/reset")
async def reset_parameters(p: Principal = Depends(require_official), store: Store = Depends(get_store)) -> dict:
    await store.delete("engine_parameters", DOCUMENT_ID)
    return await get_parameters(p=p, store=store)
