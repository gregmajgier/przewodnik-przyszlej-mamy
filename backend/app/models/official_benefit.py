from datetime import datetime

from ..mocks.benefit import Benefit  # MOCK planu 03 — patrz NOTES-MOCKS.md


class OfficialBenefit(Benefit):
    """Świadczenie w panelu urzędnika (plan 07): `Benefit` + stan zatwierdzenia warunków i metadane edycji."""

    conditions_approved: bool = False
    created_by: str | None = None
    updated_at: datetime | None = None
