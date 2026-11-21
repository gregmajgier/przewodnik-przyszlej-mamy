from datetime import datetime
from typing import Literal

from .benefit import Benefit


class OfficialBenefit(Benefit):
    """Świadczenie w panelu urzędnika (plan 07): `Benefit` + stan zatwierdzenia warunków i metadane edycji."""

    # edytor urzędnika może zapisać szkic bez tych pól — uzupełnia je przy publikacji
    category: Literal["benefit", "perk"] = "benefit"
    how_to_apply: str = ""
    source_url: str = ""
    conditions_approved: bool = False
    created_by: str | None = None
    updated_at: datetime | None = None
