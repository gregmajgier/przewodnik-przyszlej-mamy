from typing import Literal

from pydantic import BaseModel


class User(BaseModel):
    id: str
    role: Literal["parent", "official"]
    name: str
    email: str | None = None
    persona_id: str | None = None
    family_id: str | None = None
    unit_id: str | None = None
