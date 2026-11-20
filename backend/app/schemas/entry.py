from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class EntryCreate(BaseModel):
    title: Optional[str] = None
    content: str = Field(..., min_length=1)
    is_manual_emotion_tag: bool = False


class EntryOut(BaseModel):
    id: str
    user_id: str
    notebook_id: str
    entry_date: date
    title: Optional[str] = None
    content: str
    is_manual_emotion_tag: bool
    is_crisis_flagged: bool
    tone_scores: dict = {}
    created_at: datetime
    updated_at: datetime


class TodayStatus(BaseModel):
    today_count: int
    daily_limit: int
    entries: list[EntryOut]


class CrisisNotice(BaseModel):
    is_crisis: bool
    hotline_number: str = "109"
    message: str = ""


class EntryCreateResponse(BaseModel):
    entry: EntryOut
    crisis: CrisisNotice
