"""Status AI (tryb demo/live) oraz obsługa przekroczenia limitów AI (429 + Retry-After)."""

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from ..ai.limits import AILimitExceeded
from ..config import settings
from ..security import Principal, current_principal

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/status")
async def ai_status(_: Principal = Depends(current_principal)) -> dict:
    live = bool(settings.azure_openai_endpoint and settings.azure_openai_api_key)
    return {"mode": "live" if live else "demo", "available": True}


def install(app: FastAPI) -> None:
    """Wołane przez `create_app`: rejestruje obsługę `AILimitExceeded`."""

    @app.exception_handler(AILimitExceeded)
    async def ai_limit_handler(_: Request, exc: AILimitExceeded) -> JSONResponse:
        return JSONResponse(
            {"detail": exc.detail}, status_code=429, headers={"Retry-After": str(exc.retry_after)}
        )
