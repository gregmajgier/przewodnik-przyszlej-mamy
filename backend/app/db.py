from azure.cosmos.aio import CosmosClient

from .config import settings

_client: CosmosClient | None = None


async def init_db() -> None:
    global _client
    if not settings.cosmos_endpoint:
        return
    _client = CosmosClient(settings.cosmos_endpoint, credential=settings.cosmos_key)
    await _client.create_database_if_not_exists(settings.cosmos_database)


async def close_db() -> None:
    if _client:
        await _client.close()


def get_database():
    if _client is None:
        raise RuntimeError("Cosmos DB is not configured (set COSMOS_ENDPOINT / COSMOS_KEY)")
    return _client.get_database_client(settings.cosmos_database)
