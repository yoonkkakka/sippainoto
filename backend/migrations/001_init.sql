-- 실패작 노트 — 전체 스키마 (Phase 1~4 통합)
-- 기획서.md 섹션 4.1 / 9 / 10의 결정 사항을 그대로 반영.
--
-- ⚠️ 이 스크립트는 몇 번을 다시 실행해도 안전(idempotent)하도록 작성되어 있습니다.
-- 이미 일부 테이블이 있어도 "already exists" 오류 없이, 기존 데이터는 그대로 두고
-- 없는 테이블/컬럼/함수/트리거/정책만 채워 넣습니다. 안심하고 다시 실행하세요.

create extension if not exists "pgcrypto";

-- =========================================================
-- 1. profiles: auth.users와 분리된 사용자 프로필
--    app_lock_enabled: '생체인증 잠금' 사용 여부(Phase 4). 실제 생체 인증
--    프롬프트(WebAuthn/플랫폼 API)는 프론트엔드 담당이며, 여기서는 on/off만 보관.
-- =========================================================
create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    nickname text not null default '익명',
    timezone text not null default 'Asia/Seoul',
    app_lock_enabled boolean not null default false,
    created_at timestamptz not null default now()
);

-- 기존 profiles 테이블이 이전 버전 스크립트로 만들어져 있어도, 데이터는 그대로 두고
-- 빠진 컬럼만 채워 넣는다.
alter table public.profiles add column if not exists nickname text not null default '익명';
alter table public.profiles add column if not exists timezone text not null default 'Asia/Seoul';
alter table public.profiles add column if not exists app_lock_enabled boolean not null default false;
alter table public.profiles add column if not exists created_at timestamptz not null default now();

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.profiles (id, nickname)
    values (new.id, coalesce(nullif(split_part(new.email, '@', 1), ''), '익명'))
    on conflict (id) do nothing;
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute procedure public.handle_new_user();

-- =========================================================
-- 2. notebooks: 권 단위 (실패작 노트 / 감정 노트)
-- =========================================================
create table if not exists public.notebooks (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.profiles(id) on delete cascade,
    volume_no integer not null,
    type text not null check (type in ('failure', 'emotion')),
    status text not null default 'in_progress' check (status in ('in_progress', 'completed')),
    page_limit integer not null default 155,
    started_at timestamptz not null default now(),
    completed_at timestamptz,
    unique (user_id, type, volume_no)
);

-- =========================================================
-- 3. entries: 한 장 (하루 최대 5장)
-- =========================================================
create table if not exists public.entries (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.profiles(id) on delete cascade,
    notebook_id uuid not null references public.notebooks(id) on delete cascade,
    entry_date date not null, -- 사용자 로컬 타임존 기준 날짜. FastAPI에서 profiles.timezone으로 계산해 전달.
    title text,
    content text not null,
    is_manual_emotion_tag boolean not null default false,
    is_crisis_flagged boolean not null default false, -- 109 위기 감지 결과 (Phase 2)
    tone_scores jsonb not null default '{}'::jsonb,    -- 카테고리별 톤 점수 (Phase 2)
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.entries add column if not exists is_manual_emotion_tag boolean not null default false;
alter table public.entries add column if not exists is_crisis_flagged boolean not null default false;
alter table public.entries add column if not exists tone_scores jsonb not null default '{}'::jsonb;
alter table public.entries add column if not exists updated_at timestamptz not null default now();

create index if not exists entries_user_date_idx on public.entries (user_id, entry_date);
create index if not exists entries_notebook_idx on public.entries (notebook_id);

-- 하루 최대 5장 제한을 DB 레벨에서 강제 (기획서 섹션 2.1 / 10)
create or replace function public.check_daily_entry_limit()
returns trigger
language plpgsql
as $$
declare
    today_count integer;
begin
    select count(*) into today_count
    from public.entries
    where user_id = new.user_id
      and entry_date = new.entry_date;

    if today_count >= 5 then
        raise exception '하루에 최대 5장까지만 작성할 수 있습니다.' using errcode = 'P0001';
    end if;

    return new;
end;
$$;

drop trigger if exists entries_daily_limit on public.entries;
create trigger entries_daily_limit
before insert on public.entries
for each row execute procedure public.check_daily_entry_limit();

-- 작성된 글의 내용(content/title/entry_date)은 수정 불가 — 소속 노트(notebook_id)와
-- 톤 점수(tone_scores), 수동 태그 여부만 변경 가능.
create or replace function public.prevent_entry_content_update()
returns trigger
language plpgsql
as $$
begin
    if new.content <> old.content
        or new.title is distinct from old.title
        or new.entry_date <> old.entry_date then
        raise exception '작성된 글의 내용은 수정할 수 없습니다.' using errcode = 'P0001';
    end if;
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists entries_prevent_content_update on public.entries;
create trigger entries_prevent_content_update
before update on public.entries
for each row execute procedure public.prevent_entry_content_update();

-- =========================================================
-- 4. keyword_dictionary: 감정 노트 분류 / 109 위기 감지용 단어 사전 (Phase 2)
--    외부 AI API 없이, 이 테이블의 단어·가중치만으로 서버가 직접 점수를 계산한다.
-- =========================================================
create table if not exists public.keyword_dictionary (
    id uuid primary key default gen_random_uuid(),
    term text not null,
    category text not null check (
        category in (
            'tone_depression',       -- 우울
            'tone_helplessness',     -- 무기력
            'tone_self_deprecation', -- 자기비하
            'tone_anger',            -- 분노
            'crisis'                 -- 109 위기(자살/자해 암시) 감지 전용
        )
    ),
    weight numeric not null default 1.0,
    is_active boolean not null default true,
    updated_at timestamptz not null default now()
);

create index if not exists keyword_dictionary_category_active_idx
    on public.keyword_dictionary (category)
    where is_active;

-- 시드 데이터를 중복 삽입하지 않도록 (term, category) 조합에 유니크 인덱스를 둔다.
create unique index if not exists keyword_dictionary_term_category_key
    on public.keyword_dictionary (term, category);

-- =========================================================
-- 5. exports: 출판본 (Phase 3)
-- =========================================================
create table if not exists public.exports (
    id uuid primary key default gen_random_uuid(),
    notebook_id uuid not null references public.notebooks(id) on delete cascade,
    binding_style text not null check (binding_style in ('kr', 'jp')),
    cover_theme text not null default 'mono',
    storage_path text not null, -- Supabase Storage 'exports' 버킷 내 경로 (비공개, 서명 URL로만 접근)
    created_at timestamptz not null default now()
);

-- =========================================================
-- 6. RLS: 본인 데이터만 조회/작성 가능. DELETE 정책은 두지 않아 삭제 자체가 불가능.
-- =========================================================
alter table public.profiles enable row level security;
alter table public.notebooks enable row level security;
alter table public.entries enable row level security;
alter table public.keyword_dictionary enable row level security;
alter table public.exports enable row level security;

drop policy if exists "본인 프로필만 조회/수정" on public.profiles;
create policy "본인 프로필만 조회/수정" on public.profiles
    for all using (auth.uid() = id) with check (auth.uid() = id);

drop policy if exists "본인 노트북만 조회/작성/수정" on public.notebooks;
create policy "본인 노트북만 조회/작성/수정" on public.notebooks
    for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "본인 글만 조회" on public.entries;
create policy "본인 글만 조회" on public.entries
    for select using (auth.uid() = user_id);

-- user_id만 본인인지 확인하는 것으로는 부족하다 — notebook_id가 실제로 본인 소유
-- 노트북인지도 함께 확인해야, 남의 notebook_id를 끼워넣는 것을 막을 수 있다.
drop policy if exists "본인 글만 작성" on public.entries;
create policy "본인 글만 작성" on public.entries
    for insert with check (
        auth.uid() = user_id
        and exists (
            select 1 from public.notebooks n
            where n.id = entries.notebook_id and n.user_id = auth.uid()
        )
    );

drop policy if exists "본인 글의 소속 노트/점수만 변경" on public.entries;
create policy "본인 글의 소속 노트/점수만 변경" on public.entries
    for update using (auth.uid() = user_id) with check (
        auth.uid() = user_id
        and exists (
            select 1 from public.notebooks n
            where n.id = entries.notebook_id and n.user_id = auth.uid()
        )
    );

drop policy if exists "본인 글만 삭제" on public.entries;
create policy "본인 글만 삭제" on public.entries
    for delete using (auth.uid() = user_id);

-- 전체 로그인 사용자에게 읽기만 허용. 쓰기 정책은 두지 않아
-- Supabase 대시보드(Table Editor, service_role)에서만 추가/수정 가능.
drop policy if exists "모든 로그인 사용자 읽기 가능" on public.keyword_dictionary;
create policy "모든 로그인 사용자 읽기 가능" on public.keyword_dictionary
    for select
    to authenticated
    using (true);

drop policy if exists "본인 노트북의 출판물만 조회" on public.exports;
create policy "본인 노트북의 출판물만 조회" on public.exports
    for select
    using (exists (
        select 1 from public.notebooks n
        where n.id = exports.notebook_id and n.user_id = auth.uid()
    ));

drop policy if exists "본인 노트북의 출판물만 생성" on public.exports;
create policy "본인 노트북의 출판물만 생성" on public.exports
    for insert
    with check (exists (
        select 1 from public.notebooks n
        where n.id = exports.notebook_id and n.user_id = auth.uid()
    ));

-- =========================================================
-- 7. Storage: PDF 출판본을 담을 비공개 버킷 (Phase 3)
-- =========================================================
insert into storage.buckets (id, name, public)
values ('exports', 'exports', false)
on conflict (id) do nothing;

-- 업로드/다운로드 경로는 백엔드가 `{user_id}/{notebook_id}/{timestamp}.pdf` 형태로 만든다.
-- 경로의 첫 폴더(=user_id)가 본인 것일 때만 읽고 쓸 수 있게 제한.
drop policy if exists "본인 출판물만 업로드" on storage.objects;
create policy "본인 출판물만 업로드" on storage.objects
    for insert
    to authenticated
    with check (bucket_id = 'exports' and (storage.foldername(name))[1] = auth.uid()::text);

drop policy if exists "본인 출판물만 조회" on storage.objects;
create policy "본인 출판물만 조회" on storage.objects
    for select
    to authenticated
    using (bucket_id = 'exports' and (storage.foldername(name))[1] = auth.uid()::text);

-- =========================================================
-- 8. keyword_dictionary 시드 데이터 (이미 들어있는 단어는 건드리지 않음)
-- ⚠️ 아래 값은 "동작을 보여주기 위한 예시"일 뿐, 실제 서비스에 쓸 수 있는 공식 데이터가
-- 아닙니다. 실제 운영 전 반드시 다음으로 교체/보강하고 전문가 검토를 받아야 합니다:
--   - 톤 분류(tone_*): 공개 한국어 감성사전(예: KNU 한국어 감성사전)을 가져와 이식
--   - 위기(crisis): 보건복지부·정신건강 관련 기관이 공개한 위기 선별 키워드 가이드를 참고해 구성
-- =========================================================
insert into public.keyword_dictionary (term, category, weight) values
    ('무기력', 'tone_helplessness', 2.0),
    ('아무것도 하기 싫다', 'tone_helplessness', 2.5),
    ('의욕이 없다', 'tone_helplessness', 2.0),
    ('나는 쓸모없다', 'tone_self_deprecation', 3.0),
    ('내가 문제야', 'tone_self_deprecation', 2.0),
    ('나는 왜 이럴까', 'tone_self_deprecation', 1.5),
    ('우울하다', 'tone_depression', 2.0),
    ('눈물이 난다', 'tone_depression', 1.5),
    ('마음이 무겁다', 'tone_depression', 1.5),
    ('화가 난다', 'tone_anger', 1.5),
    ('짜증난다', 'tone_anger', 1.0),
    ('죽고 싶다', 'crisis', 10.0),
    ('사라지고 싶다', 'crisis', 8.0),
    ('더 이상 살고 싶지 않다', 'crisis', 10.0),
    ('자살하고 싶다', 'crisis', 10.0)
on conflict (term, category) do nothing;
