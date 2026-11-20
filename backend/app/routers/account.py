from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_current_user
from app.schemas.account import ProfileOut, ProfileSettingsUpdate

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/profile", response_model=ProfileOut)
async def get_profile(current_user: dict = Depends(get_current_user)) -> dict:
    client = current_user["client"]
    result = client.table("profiles").select("*").eq("id", current_user["id"]).single().execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="프로필을 찾을 수 없습니다.")
    return result.data


@router.patch("/profile", response_model=ProfileOut)
async def update_profile(payload: ProfileSettingsUpdate, current_user: dict = Depends(get_current_user)) -> dict:
    """닉네임/타임존 변경, 그리고 '생체인증 잠금' 사용 여부(app_lock_enabled) 토글.
    실제 생체 인증 프롬프트(WebAuthn/플랫폼 생체 API)는 프론트엔드가 담당하고,
    백엔드는 그 on/off 설정값만 보관한다 — 이 저장소에는 아직 프론트엔드가 없어 UI 연동은 Phase 4 이후 과제."""
    client = current_user["client"]
    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}

    if not updates:
        result = client.table("profiles").select("*").eq("id", current_user["id"]).single().execute()
        return result.data

    result = client.table("profiles").update(updates).eq("id", current_user["id"]).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="업데이트에 실패했습니다.")
    return result.data[0]


@router.get("/data-export")
async def export_my_data(current_user: dict = Depends(get_current_user)) -> dict:
    """데이터 백업/내보내기 — 155장 완결 시의 PDF '출판'과는 별개로,
    프로필+노트북+글 전체를 JSON으로 그대로 내려받을 수 있게 한다."""
    client = current_user["client"]
    user_id = current_user["id"]

    profile = client.table("profiles").select("*").eq("id", user_id).single().execute().data
    notebooks = client.table("notebooks").select("*").eq("user_id", user_id).execute().data
    entries = (
        client.table("entries")
        .select("*")
        .eq("user_id", user_id)
        .order("entry_date")
        .execute()
        .data
    )

    return {"profile": profile, "notebooks": notebooks, "entries": entries}
