from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.auth import get_current_user
from app.schemas.export import ExportOut, ExportRequest
from app.services.pdf import render_notebook_html, render_pdf

router = APIRouter(tags=["exports"])

SIGNED_URL_EXPIRES_IN = 60 * 60  # 1시간
STORAGE_BUCKET = "exports"


def _extract_signed_url(signed: dict) -> str:
    return signed.get("signedURL") or signed.get("signed_url") or ""


@router.post("/notebooks/{notebook_id}/export", response_model=ExportOut, status_code=status.HTTP_201_CREATED)
async def export_notebook(
    notebook_id: str,
    payload: ExportRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """동기 처리: 요청 즉시 PDF를 생성해 서명된 다운로드 링크와 함께 응답한다."""
    client = current_user["client"]
    user_id = current_user["id"]

    notebook_result = (
        client.table("notebooks").select("*").eq("id", notebook_id).eq("user_id", user_id).limit(1).execute()
    )
    if not notebook_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="노트북을 찾을 수 없습니다.")
    notebook = notebook_result.data[0]

    if notebook["status"] != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="아직 완결되지 않은 노트북은 출판할 수 없습니다. (155장을 채워야 출판 가능)",
        )

    entries = (
        client.table("entries")
        .select("entry_date, title, content")
        .eq("notebook_id", notebook_id)
        .order("entry_date")
        .order("created_at")
        .execute()
    ).data

    profile = client.table("profiles").select("nickname").eq("id", user_id).single().execute()
    nickname = profile.data["nickname"] if profile.data else "익명"

    html = render_notebook_html(notebook, entries, nickname, payload.binding_style, payload.cover_theme)
    pdf_bytes = await render_pdf(request.app.state.browser, html)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    storage_path = f"{user_id}/{notebook_id}/{timestamp}.pdf"

    client.storage.from_(STORAGE_BUCKET).upload(
        storage_path,
        pdf_bytes,
        {"content-type": "application/pdf"},
    )

    inserted = (
        client.table("exports")
        .insert(
            {
                "notebook_id": notebook_id,
                "binding_style": payload.binding_style,
                "cover_theme": payload.cover_theme,
                "storage_path": storage_path,
            }
        )
        .execute()
    )
    if not inserted.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="출판 기록 저장에 실패했습니다.")
    export_row = inserted.data[0]

    signed = client.storage.from_(STORAGE_BUCKET).create_signed_url(storage_path, SIGNED_URL_EXPIRES_IN)

    return {**export_row, "download_url": _extract_signed_url(signed)}


@router.get("/exports", response_model=list[ExportOut])
async def list_exports(current_user: dict = Depends(get_current_user)) -> list[dict]:
    """RLS가 이미 '본인 노트북의 출판물'만 돌려주므로 별도 필터가 필요 없다."""
    client = current_user["client"]

    exports = client.table("exports").select("*").order("created_at", desc=True).execute().data

    results = []
    for row in exports:
        signed = client.storage.from_(STORAGE_BUCKET).create_signed_url(row["storage_path"], SIGNED_URL_EXPIRES_IN)
        results.append({**row, "download_url": _extract_signed_url(signed)})
    return results
