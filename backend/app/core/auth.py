from fastapi import Header, HTTPException, status

from app.core.supabase_client import get_anon_client, get_user_client


async def get_current_user(authorization: str = Header(...)) -> dict:
    """Authorization: Bearer <supabase access token> 를 검증하고,
    이후 모든 DB 접근이 해당 사용자의 RLS 범위 안에서 이루어지도록
    사용자 토큰이 실린 Supabase 클라이언트를 함께 돌려준다."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증 토큰이 필요합니다.")

    token = authorization.removeprefix("Bearer ").strip()

    verifying_client = get_anon_client()
    try:
        user_response = verifying_client.auth.get_user(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 토큰입니다.")

    user = user_response.user if user_response else None
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 토큰입니다.")

    return {
        "id": user.id,
        "email": user.email,
        "client": get_user_client(token),
    }
