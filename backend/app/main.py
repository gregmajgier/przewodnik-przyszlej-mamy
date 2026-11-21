from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .config import settings
from .routers import wnioski


@asynccontextmanager
async def lifespan(_: FastAPI):
    await db.init_db()
    yield
    await db.close_db()


app = FastAPI(title="mrodzina API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(wnioski.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
