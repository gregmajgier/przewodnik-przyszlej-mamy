import importlib
import pkgutil
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import db, routers
from .config import settings
from .errors import DomainError
from .security import validate_startup_config
from .seed import seed_all
from .storage import CosmosStore, MemoryStore, Store


def _include_routers(app: FastAPI) -> None:
    """Dołącza każdy moduł z `app/routers/` eksponujący `router`."""
    for info in pkgutil.iter_modules(routers.__path__):
        module = importlib.import_module(f"{routers.__name__}.{info.name}")
        router = getattr(module, "router", None)
        if router is not None:
            app.include_router(router)
        install = getattr(module, "install", None)  # opcjonalny hak: handlery wyjątków itp.
        if callable(install):
            install(app)


def create_app(store: Store | None = None) -> FastAPI:
    """Buduje aplikację. Bez `store`: Cosmos gdy ustawiono `COSMOS_ENDPOINT`, inaczej MemoryStore."""
    use_cosmos = store is None and bool(settings.cosmos_endpoint)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        validate_startup_config()
        if use_cosmos:
            await db.init_db()
            app.state.store = CosmosStore(db.get_database())
        await seed_all(app.state.store)
        yield
        if use_cosmos:
            await db.close_db()

    app = FastAPI(title="mrodzina API", lifespan=lifespan)
    if not use_cosmos:
        app.state.store = store if store is not None else MemoryStore()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(DomainError)
    async def domain_error_handler(_: Request, exc: DomainError):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    _include_routers(app)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
