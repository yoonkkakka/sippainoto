from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from supabase import Client

PAGE_LIMIT = 155
DEFAULT_TIMEZONE = "Asia/Seoul"


def get_user_timezone(client: Client, user_id: str) -> str:
    result = client.table("profiles").select("timezone").eq("id", user_id).single().execute()
    if result.data and result.data.get("timezone"):
        return result.data["timezone"]
    return DEFAULT_TIMEZONE


def today_in_user_timezone(client: Client, user_id: str):
    tz_name = get_user_timezone(client, user_id)
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo(DEFAULT_TIMEZONE)
    return datetime.now(tz).date()


def get_or_create_current_notebook(client: Client, user_id: str, notebook_type: str) -> dict:
    """해당 타입('failure'|'emotion')의 진행 중인 노트북을 찾고, 없으면 다음 권번호로 새로 만든다."""
    existing = (
        client.table("notebooks")
        .select("*")
        .eq("user_id", user_id)
        .eq("type", notebook_type)
        .eq("status", "in_progress")
        .limit(1)
        .execute()
    )
    if existing.data:
        return existing.data[0]

    last_volume = (
        client.table("notebooks")
        .select("volume_no")
        .eq("user_id", user_id)
        .eq("type", notebook_type)
        .order("volume_no", desc=True)
        .limit(1)
        .execute()
    )
    next_volume_no = (last_volume.data[0]["volume_no"] + 1) if last_volume.data else 1

    created = (
        client.table("notebooks")
        .insert(
            {
                "user_id": user_id,
                "volume_no": next_volume_no,
                "type": notebook_type,
                "status": "in_progress",
                "page_limit": PAGE_LIMIT,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .execute()
    )
    return created.data[0]


def count_notebook_entries(client: Client, notebook_id: str) -> int:
    result = client.table("entries").select("id", count="exact").eq("notebook_id", notebook_id).execute()
    return result.count or 0


def complete_notebook_if_full(client: Client, notebook: dict) -> None:
    """155장(page_limit)을 채운 노트북을 완결 처리한다. 다음 글부터는
    get_or_create_current_notebook이 자동으로 새 권을 만들어낸다."""
    if notebook["status"] == "completed":
        return

    entry_count = count_notebook_entries(client, notebook["id"])
    if entry_count >= notebook["page_limit"]:
        client.table("notebooks").update(
            {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", notebook["id"]).execute()
