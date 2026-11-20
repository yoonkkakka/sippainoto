from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.core.auth import get_current_user
from app.schemas.entry import EntryCreate, EntryCreateResponse, EntryOut, TodayStatus
from app.services.classification import (
    CRISIS_MESSAGE,
    HOTLINE_NUMBER,
    check_crisis,
    reclassify_entry_tone,
)
from app.services.notebooks import (
    complete_notebook_if_full,
    get_or_create_current_notebook,
    today_in_user_timezone,
)

router = APIRouter(prefix="/entries", tags=["entries"])

DAILY_LIMIT = 5


@router.post("", response_model=EntryCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_entry(
    payload: EntryCreate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
) -> dict:
    client = current_user["client"]
    user_id = current_user["id"]

    today = today_in_user_timezone(client, user_id)

    today_count = (
        client.table("entries")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .eq("entry_date", today.isoformat())
        .execute()
    )
    if (today_count.count or 0) >= DAILY_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="오늘은 이미 5장을 다 쓰셨어요. 내일 다시 써주세요.",
        )

    # 109 위기 감지는 생명과 직결되는 영역이라 저장 시점에 동기로 즉시 체크한다.
    is_crisis = check_crisis(client, payload.content)

    notebook_type = "emotion" if (payload.is_manual_emotion_tag or is_crisis) else "failure"
    notebook = get_or_create_current_notebook(client, user_id, notebook_type)

    inserted = (
        client.table("entries")
        .insert(
            {
                "user_id": user_id,
                "notebook_id": notebook["id"],
                "entry_date": today.isoformat(),
                "title": payload.title,
                "content": payload.content,
                "is_manual_emotion_tag": payload.is_manual_emotion_tag,
                "is_crisis_flagged": is_crisis,
            }
        )
        .execute()
    )

    if not inserted.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="저장에 실패했습니다.")

    complete_notebook_if_full(client, notebook)

    entry = inserted.data[0]

    # 톤 점수 재판단은 수동 태그/위기 감지 여부와 무관하게 항상 백그라운드로 실행한다.
    # (이미 감정 노트에 있는 글이면 reclassify_entry_tone이 점수만 기록하고 이동은 생략)
    background_tasks.add_task(reclassify_entry_tone, client, entry["id"], user_id)

    return {
        "entry": entry,
        "crisis": {
            "is_crisis": is_crisis,
            "hotline_number": HOTLINE_NUMBER,
            "message": CRISIS_MESSAGE if is_crisis else "",
        },
    }


@router.get("", response_model=list[EntryOut])
async def list_entries(
    notebook_type: Optional[Literal["failure", "emotion"]] = Query(default=None),
    date_from: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    client = current_user["client"]
    user_id = current_user["id"]

    query = client.table("entries").select("*").eq("user_id", user_id)

    if notebook_type:
        notebooks = (
            client.table("notebooks")
            .select("id")
            .eq("user_id", user_id)
            .eq("type", notebook_type)
            .execute()
        )
        notebook_ids = [n["id"] for n in notebooks.data]
        if not notebook_ids:
            return []
        query = query.in_("notebook_id", notebook_ids)

    if date_from:
        query = query.gte("entry_date", date_from)
    if date_to:
        query = query.lte("entry_date", date_to)

    result = query.order("entry_date", desc=True).order("created_at", desc=True).execute()
    return result.data


@router.get("/today", response_model=TodayStatus)
async def get_today_status(current_user: dict = Depends(get_current_user)) -> dict:
    """홈 화면의 '오늘 n/5장' 표시용."""
    client = current_user["client"]
    user_id = current_user["id"]

    today = today_in_user_timezone(client, user_id)
    result = (
        client.table("entries")
        .select("*")
        .eq("user_id", user_id)
        .eq("entry_date", today.isoformat())
        .order("created_at")
        .execute()
    )
    entries = result.data
    return {"today_count": len(entries), "daily_limit": DAILY_LIMIT, "entries": entries}


@router.post("/{entry_id}/move", response_model=EntryOut)
async def move_entry(entry_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    """실패작 노트 ↔ 감정 노트 간 소속 변경(되돌리기용). 글 내용 자체는 변경하지 않는다."""
    client = current_user["client"]
    user_id = current_user["id"]

    existing = (
        client.table("entries")
        .select("*, notebooks(type)")
        .eq("id", entry_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="글을 찾을 수 없습니다.")

    entry = existing.data[0]
    current_type = entry["notebooks"]["type"]
    target_type = "failure" if current_type == "emotion" else "emotion"

    target_notebook = get_or_create_current_notebook(client, user_id, target_type)

    updated = (
        client.table("entries")
        .update(
            {
                "notebook_id": target_notebook["id"],
                "is_manual_emotion_tag": target_type == "emotion",
            }
        )
        .eq("id", entry_id)
        .execute()
    )
    if not updated.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="이동에 실패했습니다.")

    complete_notebook_if_full(client, target_notebook)

    return updated.data[0]
