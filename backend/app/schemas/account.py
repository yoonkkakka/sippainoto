from typing import Optional

from pydantic import BaseModel


class ProfileSettingsUpdate(BaseModel):
    nickname: Optional[str] = None
    timezone: Optional[str] = None
    app_lock_enabled: Optional[bool] = None


class ProfileOut(BaseModel):
    id: str
    nickname: str
    timezone: str
    app_lock_enabled: bool
