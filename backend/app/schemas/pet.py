from datetime import datetime
from typing import Literal

from pydantic import BaseModel

PetMood = Literal["happy", "normal", "sad", "angry"]


class PetState(BaseModel):
    name: str
    level: int
    exp: int
    exp_to_next: int
    affection: int
    mood: PetMood
    stage: str
    total_pats: int
    days_together: int
    last_interaction_at: datetime
