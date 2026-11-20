from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

NotebookType = Literal["failure", "emotion"]
NotebookStatus = Literal["in_progress", "completed"]


class NotebookOut(BaseModel):
    id: str
    user_id: str
    volume_no: int
    type: NotebookType
    status: NotebookStatus
    page_limit: int
    entry_count: int = 0
    started_at: datetime
    completed_at: Optional[datetime] = None
