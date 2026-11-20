from supabase import Client, create_client

from app.core.config import settings


def get_anon_client() -> Client:
    """RLS가 적용되지 않은 비인증 클라이언트 (로그인 전 단계에서만 사용)."""
    return create_client(settings.supabase_url, settings.supabase_anon_key)


def get_user_client(access_token: str) -> Client:
    """요청자의 Supabase JWT를 그대로 실어 보내, 모든 쿼리가 RLS로 범위 제한되는 클라이언트."""
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.postgrest.auth(access_token)
    return client
