"""Warstwa danych: `Store` (Protocol), `MemoryStore` (domyślny, bez Azure) i `CosmosStore`."""

import copy
import re
from typing import Any, Protocol

from fastapi import Request

COLLECTIONS = (
    "users",
    "units",
    "families",
    "join_requests",
    "profiles",
    "children",
    "contracts",
    "benefits",
    "benefit_answers",
    "applications",
    "calendar_events",
    "notifications",
    "mail_messages",
    "chat_sessions",
    "ai_usage",
)

_FIELD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_COLL_RE = _FIELD_RE


class Store(Protocol):
    async def get(self, coll: str, id: str) -> dict | None: ...

    async def put(self, coll: str, doc: dict) -> dict: ...

    async def delete(self, coll: str, id: str) -> None: ...

    async def find(self, coll: str, **eq: Any) -> list[dict]: ...


def _require_id(doc: dict) -> str:
    doc_id = doc.get("id")
    if not doc_id or not isinstance(doc_id, str):
        raise ValueError("Dokument musi mieć niepuste pole 'id'")
    return doc_id


class MemoryStore:
    """Magazyn w pamięci procesu; dokumenty są kopiowane przy zapisie i odczycie."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, dict]] = {}

    async def get(self, coll: str, id: str) -> dict | None:
        doc = self._data.get(coll, {}).get(id)
        return copy.deepcopy(doc) if doc is not None else None

    async def put(self, coll: str, doc: dict) -> dict:
        doc_id = _require_id(doc)
        stored = copy.deepcopy(doc)
        self._data.setdefault(coll, {})[doc_id] = stored
        return copy.deepcopy(stored)

    async def delete(self, coll: str, id: str) -> None:
        self._data.get(coll, {}).pop(id, None)

    async def find(self, coll: str, **eq: Any) -> list[dict]:
        return [
            copy.deepcopy(d)
            for d in self._data.get(coll, {}).values()
            if all(d.get(k) == v for k, v in eq.items())
        ]


class CosmosStore:
    """Cosmos DB (async SDK): jeden kontener na kolekcję, klucz partycji `/id`.

    `client_db` to `azure.cosmos.aio.DatabaseProxy` (lub atrapa o tym samym interfejsie).
    """

    def __init__(self, client_db: Any) -> None:
        self._db = client_db
        self._containers: dict[str, Any] = {}

    async def _container(self, coll: str) -> Any:
        if not _COLL_RE.match(coll):
            raise ValueError(f"Nieprawidłowa nazwa kolekcji: {coll!r}")
        if coll not in self._containers:
            from azure.cosmos import PartitionKey

            self._containers[coll] = await self._db.create_container_if_not_exists(
                id=coll, partition_key=PartitionKey(path="/id")
            )
        return self._containers[coll]

    @staticmethod
    def _clean(doc: dict) -> dict:
        return {k: v for k, v in doc.items() if not k.startswith("_")}

    async def get(self, coll: str, id: str) -> dict | None:
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        container = await self._container(coll)
        try:
            doc = await container.read_item(item=id, partition_key=id)
        except CosmosResourceNotFoundError:
            return None
        return self._clean(doc)

    async def put(self, coll: str, doc: dict) -> dict:
        _require_id(doc)
        container = await self._container(coll)
        saved = await container.upsert_item(body=copy.deepcopy(doc))
        return self._clean(saved)

    async def delete(self, coll: str, id: str) -> None:
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        container = await self._container(coll)
        try:
            await container.delete_item(item=id, partition_key=id)
        except CosmosResourceNotFoundError:
            pass

    async def find(self, coll: str, **eq: Any) -> list[dict]:
        for field in eq:
            if not _FIELD_RE.match(field):
                raise ValueError(f"Nieprawidłowa nazwa pola: {field!r}")
        container = await self._container(coll)
        where = " AND ".join(f"c.{f} = @{f}" for f in eq)
        query = "SELECT * FROM c" + (f" WHERE {where}" if where else "")
        params = [{"name": f"@{f}", "value": v} for f, v in eq.items()]
        items = container.query_items(query=query, parameters=params)
        return [self._clean(d) async for d in items]


def get_store(request: Request) -> Store:
    """Zależność FastAPI: magazyn danych aplikacji."""
    return request.app.state.store
