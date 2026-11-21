"""Tokeny sesji (HMAC), hasła urzędników i zależności FastAPI do autoryzacji."""

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException

from .config import settings
from .storage import Store, get_store


class AuthError(Exception):
    """Token nieprawidłowy, podrobiony lub wygasły."""


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: str  # "parent" | "official"
    family_id: str | None = None
    unit_id: str | None = None


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload_b64: str) -> str:
    mac = hmac.new(settings.session_secret.encode(), payload_b64.encode("ascii"), hashlib.sha256)
    return _b64e(mac.digest())


def issue_token(principal: Principal, ttl_hours: float | None = None) -> str:
    ttl = settings.session_ttl_hours if ttl_hours is None else ttl_hours
    payload = {
        "uid": principal.user_id,
        "role": principal.role,
        "fid": principal.family_id,
        "unit": principal.unit_id,
        "exp": time.time() + ttl * 3600,
    }
    payload_b64 = _b64e(json.dumps(payload, separators=(",", ":")).encode())
    return f"{payload_b64}.{_sign(payload_b64)}"


def verify_token(token: str) -> Principal:
    try:
        payload_b64, sig = token.split(".")
        if not hmac.compare_digest(sig.encode("ascii"), _sign(payload_b64).encode("ascii")):
            raise AuthError("Nieprawidłowy podpis tokenu")
        payload = json.loads(_b64d(payload_b64))
        if float(payload["exp"]) <= time.time():
            raise AuthError("Token wygasł")
        return Principal(payload["uid"], payload["role"], payload.get("fid"), payload.get("unit"))
    except AuthError:
        raise
    except (ValueError, KeyError, TypeError, UnicodeError, binascii.Error) as e:
        raise AuthError("Nieprawidłowy token") from e


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        scheme, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
        return hmac.compare_digest(expected, bytes.fromhex(digest_hex))
    except ValueError:
        return False


def _unauthorized(detail: str = "Wymagane logowanie. Zaloguj się ponownie.") -> HTTPException:
    return HTTPException(401, detail, headers={"WWW-Authenticate": "Bearer"})


async def current_principal(
    authorization: str | None = Header(default=None),
    store: Store = Depends(get_store),
) -> Principal:
    """Zalogowany użytkownik; `family_id` i `unit_id` są zawsze świeże (z bazy, nie z tokenu)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _unauthorized()
    try:
        claims = verify_token(authorization[7:].strip())
    except AuthError:
        raise _unauthorized("Sesja jest nieprawidłowa lub wygasła. Zaloguj się ponownie.") from None
    user = await store.get("users", claims.user_id)
    if user is None:
        raise _unauthorized("Konto nie istnieje. Zaloguj się ponownie.")
    return Principal(user["id"], user["role"], user.get("family_id"), user.get("unit_id"))


async def require_parent(p: Principal = Depends(current_principal)) -> Principal:
    if p.role != "parent":
        raise HTTPException(403, "Ta czynność jest dostępna tylko dla rodzica.")
    return p


async def require_official(p: Principal = Depends(current_principal)) -> Principal:
    if p.role != "official":
        raise HTTPException(403, "Ta czynność jest dostępna tylko dla urzędnika.")
    return p
