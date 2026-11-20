from typing import Optional

from pydantic import BaseModel


class NotebookProgress(BaseModel):
    volume_no: int
    status: str
    entry_count: int
    page_limit: int


class StatsOverview(BaseModel):
    total_entries: int
    completed_notebooks: dict[str, int]
    current_progress: dict[str, Optional[NotebookProgress]]
    tone_category_totals: dict[str, float]
