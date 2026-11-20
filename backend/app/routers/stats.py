from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.schemas.stats import StatsOverview
from app.services.notebooks import count_notebook_entries

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview", response_model=StatsOverview)
async def get_overview(current_user: dict = Depends(get_current_user)) -> dict:
    """'실패 유형별 분석' — 완결 권수, 진행 중인 권의 진행률, 톤 카테고리별 누적 점수."""
    client = current_user["client"]
    user_id = current_user["id"]

    total_entries_result = client.table("entries").select("id", count="exact").eq("user_id", user_id).execute()
    total_entries = total_entries_result.count or 0

    notebooks = client.table("notebooks").select("*").eq("user_id", user_id).execute().data

    completed_notebooks = {"failure": 0, "emotion": 0}
    current_progress: dict[str, dict | None] = {"failure": None, "emotion": None}
    for nb in notebooks:
        if nb["status"] == "completed":
            completed_notebooks[nb["type"]] += 1
        else:
            current_progress[nb["type"]] = {
                "volume_no": nb["volume_no"],
                "status": nb["status"],
                "entry_count": count_notebook_entries(client, nb["id"]),
                "page_limit": nb["page_limit"],
            }

    entries = client.table("entries").select("tone_scores").eq("user_id", user_id).execute().data
    tone_totals: dict[str, float] = {}
    for entry in entries:
        for category, score in (entry.get("tone_scores") or {}).items():
            tone_totals[category] = tone_totals.get(category, 0.0) + float(score)
    tone_totals = {category: round(score, 2) for category, score in tone_totals.items()}

    return {
        "total_entries": total_entries,
        "completed_notebooks": completed_notebooks,
        "current_progress": current_progress,
        "tone_category_totals": tone_totals,
    }
