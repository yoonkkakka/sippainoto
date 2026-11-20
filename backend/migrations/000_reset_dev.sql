-- ⚠️ 이 파일은 지금 당장은 필요 없습니다. 001_init.sql이 이제 몇 번을 다시 실행해도
-- 안전(idempotent)하도록 바뀌어서, 기존 데이터를 지우지 않고도 "already exists" 오류를
-- 해결할 수 있습니다. 이 파일은 정말로 전부 밀고 처음부터 다시 만들고 싶을 때만,
-- 그리고 그래도 괜찮다는 것을 확실히 한 뒤에만 사용하세요.
--
-- 개발 중 처음부터 다시 시작하고 싶을 때만 실행하는 리셋 스크립트입니다.
-- profiles/notebooks/entries/keyword_dictionary/exports 테이블과 관련 함수·트리거,
-- 그리고 PDF용 'exports' Storage 버킷을 전부 삭제합니다.
-- 지우면 안 되는 데이터가 이미 들어있다면 실행하지 마세요.

drop table if exists public.exports cascade;
drop table if exists public.entries cascade;
drop table if exists public.notebooks cascade;
drop table if exists public.keyword_dictionary cascade;
drop table if exists public.profiles cascade;

drop trigger if exists on_auth_user_created on auth.users;

drop function if exists public.handle_new_user() cascade;
drop function if exists public.check_daily_entry_limit() cascade;
drop function if exists public.prevent_entry_content_update() cascade;

-- Storage: exports 버킷 안에 파일이 남아있으면 버킷 삭제가 막힐 수 있습니다.
-- 그럴 땐 Supabase 대시보드 Storage 메뉴에서 exports 버킷 내용을 먼저 비우세요.
drop policy if exists "본인 출판물만 업로드" on storage.objects;
drop policy if exists "본인 출판물만 조회" on storage.objects;
delete from storage.buckets where id = 'exports';

-- 이 스크립트 실행 후 migrations/001_init.sql을 다시 실행하면 깨끗한 상태로 시작됩니다.
