from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_current_user
from app.schemas.notebook import NotebookOut
from app.services.notebooks import count_notebook_entries

router = APIRouter(prefix="/notebooks", tags=["notebooks"])


@router.get("", response_model=list[NotebookOut])
async def list_notebooks(current_user: dict = Depends(get_current_user)) -> list[dict]:
    client = current_user["client"]
    user_id = current_user["id"]

    notebooks = (
        client.table("notebooks")
        .select("*")
        .eq("user_id", user_id)
        .order("type")
        .order("volume_no")
        .execute()
    ).data

    return [{**nb, "entry_count": count_notebook_entries(client, nb["id"])} for nb in notebooks]


@router.get("/{notebook_id}")
async def get_notebook(notebook_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    client = current_user["client"]
    user_id = current_user["id"]

    notebook = (
        client.table("notebooks")
        .select("*")
        .eq("id", notebook_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not notebook.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="노트북을 찾을 수 없습니다.")

    entries = (
        client.table("entries")
        .select("*")
        .eq("notebook_id", notebook_id)
        .order("entry_date")
        .order("created_at")
        .execute()
    ).data

    return {**notebook.data[0], "entry_count": len(entries), "entries": entries}
