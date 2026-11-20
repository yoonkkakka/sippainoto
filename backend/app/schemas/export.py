from datetime import datetime
from typing import Literal

from pydantic import BaseModel

BindingStyle = Literal["kr", "jp"]


class ExportRequest(BaseModel):
    binding_style: BindingStyle = "kr"
    cover_theme: str = "mono"


class ExportOut(BaseModel):
    id: str
    notebook_id: str
    binding_style: BindingStyle
    cover_theme: str
    download_url: str
    created_at: datetime
