import pytest

from app.storage import CosmosStore, MemoryStore


async def test_put_get_roundtrip():
    s = MemoryStore()
    await s.put("users", {"id": "u1", "name": "Anna"})
    assert await s.get("users", "u1") == {"id": "u1", "name": "Anna"}
    assert await s.get("users", "missing") is None


async def test_put_is_upsert():
    s = MemoryStore()
    await s.put("users", {"id": "u1", "name": "Anna"})
    await s.put("users", {"id": "u1", "name": "Ania"})
    assert (await s.get("users", "u1"))["name"] == "Ania"
    assert len(await s.find("users")) == 1


async def test_find_filters_equality():
    s = MemoryStore()
    await s.put("children", {"id": "c1", "family_id": "f1", "name": "A"})
    await s.put("children", {"id": "c2", "family_id": "f2", "name": "B"})
    await s.put("children", {"id": "c3", "family_id": "f1", "name": "C"})
    found = await s.find("children", family_id="f1")
    assert sorted(d["id"] for d in found) == ["c1", "c3"]
    assert await s.find("children", family_id="f1", name="C") == [
        {"id": "c3", "family_id": "f1", "name": "C"}
    ]
    assert len(await s.find("children")) == 3


async def test_delete_removes():
    s = MemoryStore()
    await s.put("users", {"id": "u1"})
    await s.delete("users", "u1")
    assert await s.get("users", "u1") is None
    await s.delete("users", "u1")  # idempotentne


async def test_put_requires_id():
    s = MemoryStore()
    with pytest.raises(ValueError):
        await s.put("users", {"name": "bez id"})


async def test_get_returns_copy():
    s = MemoryStore()
    await s.put("users", {"id": "u1", "tags": ["a"]})
    doc = await s.get("users", "u1")
    doc["tags"].append("b")
    doc["name"] = "zmiana"
    assert await s.get("users", "u1") == {"id": "u1", "tags": ["a"]}


async def test_put_stores_copy():
    s = MemoryStore()
    doc = {"id": "u1", "tags": ["a"]}
    await s.put("users", doc)
    doc["tags"].append("b")
    assert (await s.get("users", "u1"))["tags"] == ["a"]


class _FakeContainer:
    def __init__(self):
        self.docs: dict[str, dict] = {}
        self.queries: list[tuple[str, list]] = []

    async def upsert_item(self, body):
        self.docs[body["id"]] = body
        return body

    async def read_item(self, item, partition_key):
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        if item not in self.docs:
            raise CosmosResourceNotFoundError(message="nie ma")
        return self.docs[item]

    async def delete_item(self, item, partition_key):
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        if item not in self.docs:
            raise CosmosResourceNotFoundError(message="nie ma")
        del self.docs[item]

    def query_items(self, query, parameters=None, **kwargs):
        self.queries.append((query, parameters))

        async def gen():
            for d in self.docs.values():
                if all(d.get(p["name"][1:]) == p["value"] for p in parameters or []):
                    yield d

        return gen()


class _FakeDb:
    def __init__(self):
        self.containers: dict[str, _FakeContainer] = {}
        self.created: list[tuple[str, str]] = []

    async def create_container_if_not_exists(self, id, partition_key):
        self.created.append((id, partition_key.path))
        self.containers.setdefault(id, _FakeContainer())
        return self.containers[id]

    def get_container_client(self, id):
        return self.containers[id]


async def test_cosmos_store_roundtrip_with_fake_db():
    db = _FakeDb()
    s = CosmosStore(db)
    await s.put("users", {"id": "u1", "family_id": "f1"})
    assert ("users", "/id") in db.created
    assert await s.get("users", "u1") == {"id": "u1", "family_id": "f1"}
    assert await s.get("users", "nope") is None
    assert await s.find("users", family_id="f1") == [{"id": "u1", "family_id": "f1"}]
    assert await s.find("users", family_id="f2") == []
    await s.delete("users", "u1")
    assert await s.get("users", "u1") is None
    await s.delete("users", "u1")  # idempotentne


async def test_cosmos_store_find_uses_parameterized_query_and_validates_fields():
    db = _FakeDb()
    s = CosmosStore(db)
    await s.put("users", {"id": "u1"})
    await s.find("users", family_id="x'; DROP")
    query, params = db.containers["users"].queries[-1]
    assert "x'" not in query and "DROP" not in query
    assert params == [{"name": "@family_id", "value": "x'; DROP"}]
    with pytest.raises(ValueError):
        await s.find("users", **{"id) OR (1=1": "x"})


async def test_cosmos_store_rejects_doc_without_id():
    s = CosmosStore(_FakeDb())
    with pytest.raises(ValueError):
        await s.put("users", {"name": "x"})
