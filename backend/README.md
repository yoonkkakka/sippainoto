# 실패작 노트 — 백엔드 (Phase 1~4)

기획서.md의 로드맵 Phase 1~4를 모두 구현한 FastAPI 백엔드입니다.

- Phase 1: 회원가입/로그인, 하루 최대 5장 작성 제한, 기본 저장/조회, 155장 카운트 및 완결 처리
- Phase 2: 감정 노트 자동 분류(톤 점수), 109 위기 감지
- Phase 3: PDF 출판(한국식/일본식 제책, 표지 테마)
- Phase 4: 통계(실패 유형별 분석), 데이터 백업/내보내기, 생체인증 잠금 설정값 저장

## 1. Supabase 프로젝트 준비

1. [supabase.com](https://supabase.com)에서 새 프로젝트 생성.
2. 프로젝트의 SQL Editor에서 **`migrations/001_init.sql` 하나만** 실행 — `profiles`(생체잠금 설정 포함) / `notebooks` / `entries` / `keyword_dictionary`(예시 단어 사전 포함) / `exports` 테이블과 모든 트리거·RLS 정책, 그리고 PDF를 담을 `exports` Storage 버킷까지 한 번에 생성됩니다.
   - 이 스크립트는 **몇 번을 다시 실행해도 안전**합니다(`create table if not exists`, `alter table ... add column if not exists` 등으로 작성). 이미 테이블이 있어서 "already exists" 오류가 나더라도, 기존 데이터는 그대로 둔 채 빠진 부분만 채워 넣으니 안심하고 다시 실행하면 됩니다.
   - `migrations/000_reset_dev.sql`은 전부 삭제하고 처음부터 다시 만드는 **파괴적인** 스크립트입니다. 지우면 안 되는 데이터가 있다면 절대 실행하지 마세요 — 보통은 필요 없습니다.
3. 프로젝트 설정(Settings → API)에서 **Project URL**과 **anon public key**를 확인.
4. Authentication → Providers에서 **Email** 로그인이 켜져 있는지 확인(이메일+비밀번호만 사용, 소셜 로그인 없음).

### ⚠️ 단어 사전(keyword_dictionary)은 반드시 교체/보강하세요

`001_init.sql`에 포함된 시드 데이터는 **동작을 보여주기 위한 예시**일 뿐, 실제 서비스에 쓸 수 있는 공식 데이터가 아닙니다.

- 톤 분류(`tone_depression`/`tone_helplessness`/`tone_self_deprecation`/`tone_anger`): 공개 한국어 감성사전(예: KNU 한국어 감성사전)을 가져와 이식
- 위기(`crisis`): 보건복지부·정신건강 관련 기관이 공개한 위기 선별 키워드 가이드를 참고해 구성, 전문가 검토 필수
- 단어/가중치 수정은 코드 배포 없이 **Supabase 대시보드(Table Editor)**에서 바로 가능 (RLS상 쓰기는 대시보드/service_role에서만 허용)
- `app/services/classification.py`의 `EMOTION_SCORE_THRESHOLD`(현재 15.0)도 실제 운영 데이터를 보고 보정이 필요한 잠정값입니다.

## 2. 환경 변수

```bash
cp .env.example .env
```

`.env`에 1번에서 확인한 값을 채워 넣습니다.

```
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=xxxx
```

## 3. 실행

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --reload
```

`playwright install chromium`은 PDF 출판(Phase 3)에 쓰는 헤드리스 브라우저를 받는 과정으로, 최초 1회만 필요합니다(약 300MB 다운로드). 서버 기동 시 이 브라우저를 한 번만 띄워 재사용하므로, 요청마다 새로 켜지지 않습니다.

> WeasyPrint(HTML→PDF) 대신 Playwright(헤드리스 Chromium)를 쓰는 이유: 일본식 제책의 세로쓰기(`writing-mode: vertical-rl`)를 제대로 렌더링해야 하는데, WeasyPrint는 Windows 등에서 시스템 GTK/Pango 런타임이 없으면 아예 동작하지 않습니다. Chromium은 추가 시스템 설치 없이(바이너리만 받으면) 세로쓰기까지 안정적으로 렌더링합니다. Render 등 Linux 배포 시에는 `playwright install --with-deps chromium`으로 시스템 의존성까지 함께 설치하세요.

`http://localhost:8000/docs`에서 Swagger UI로 API를 바로 테스트할 수 있습니다.

## 4. 인증 흐름

이 백엔드는 로그인 자체를 처리하지 않습니다. 프론트엔드(또는 테스트 시 `curl`)가 Supabase Auth로 직접 로그인해서 받은 **access token**을 매 요청마다 `Authorization: Bearer <token>` 헤더로 실어 보내면, 백엔드가 그 토큰으로 사용자를 확인하고 이후 모든 DB 접근을 RLS 범위 안에서 수행합니다.

```bash
# 회원가입 (Supabase REST Auth API를 직접 호출하는 예시)
curl -X POST "$SUPABASE_URL/auth/v1/signup" \
  -H "apikey: $SUPABASE_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'

# 로그인 후 access_token 발급
curl -X POST "$SUPABASE_URL/auth/v1/token?grant_type=password" \
  -H "apikey: $SUPABASE_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
```

## 5. 구현된 엔드포인트

| Method | Path | 설명 | Phase |
|---|---|---|---|
| POST | `/entries` | 오늘의 글 작성 (하루 최대 5장, DB 트리거로 강제). 저장 시 109 위기 키워드 동기 체크 + 톤 점수 비동기 재판단 예약 | 1·2 |
| GET | `/entries` | 내 글 목록 (notebook_type/date_from/date_to 필터) | 1 |
| GET | `/entries/today` | 오늘 작성한 글 + "n/5" 카운트 (홈 화면·작성 알림 UI가 이 값을 그대로 사용) | 1 |
| POST | `/entries/{id}/move` | 실패작↔감정 노트 소속 변경(되돌리기, 오분류 정정용) — 내용 수정은 DB 트리거로 차단됨 | 1 |
| GET | `/notebooks` | 내 노트북(권) 목록 + 진행률 | 1 |
| GET | `/notebooks/{id}` | 특정 권의 페이지 목록 | 1 |
| POST | `/notebooks/{id}/export` | 완결된 권을 PDF로 출판(동기 처리). `binding_style`(kr/jp), `cover_theme` 지정 | 3 |
| GET | `/exports` | 내 출판 이력 + 다운로드용 서명 URL(1시간 유효) | 3 |
| GET | `/stats/overview` | 전체 작성 수, 완결 권수, 진행 중인 권의 진행률, 톤 카테고리별 누적 점수("실패 유형별 분석") | 4 |
| GET | `/account/profile` / PATCH | 닉네임·타임존·생체인증 잠금(app_lock_enabled) 조회/수정 | 4 |
| GET | `/account/data-export` | 내 데이터(프로필+노트북+글 전체)를 JSON으로 백업/내보내기 | 4 |

## 6. Phase 2: 분류 로직 동작 방식

- **109 위기 감지(동기)**: `POST /entries` 처리 중 `keyword_dictionary`의 `crisis` 카테고리 단어와 즉시 매칭. 글 저장은 그대로 진행하되, 감지되면 응답의 `crisis.is_crisis = true`와 함께 109 안내 메시지를 내려줌(프론트엔드가 이 값을 보고 경고 모달을 띄우는 구조) — 해당 글은 자동으로 감정 노트에 저장됨.
- **톤 점수 기반 감정 노트 분류(비동기)**: 저장 응답을 보낸 직후 `BackgroundTasks`로 `reclassify_entry_tone`을 실행. 네 카테고리별로 "가중치 × 등장 빈도를 글자 수로 정규화한 밀도" 점수를 계산해 `entries.tone_scores`에 저장하고, 합계가 `EMOTION_SCORE_THRESHOLD`를 넘으면 감정 노트로 이동.
- 수동 태그("감정 노트로 보내기")와 자동 판단은 OR 조건으로 동작: 둘 중 하나라도 감정 노트 조건을 만족하면 감정 노트에 남음. 반대로 자동 점수가 낮다고 수동 지정을 되돌리지는 않음.
- 오분류 되돌리기는 `POST /entries/{id}/move`로 처리.

## 7. Phase 3: PDF 출판 동작 방식

- `notebook.status == 'completed'`(155장 완결)인 권만 출판 가능.
- `app/templates/notebook.html`(Jinja2)로 표지·목차·본문 페이지를 HTML로 만들고, 서버에 1개만 띄워둔 Chromium으로 PDF 변환(`app/services/pdf.py`).
- `binding_style='jp'`면 본문(`.content`)에 `writing-mode: vertical-rl`을 적용해 실제 세로쓰기로 조판. 표지/목차는 두 방식 모두 가로 레이아웃 유지(제작 복잡도를 낮추기 위한 의도적 단순화).
- 생성한 PDF는 Supabase Storage의 **비공개** `exports` 버킷에 `{user_id}/{notebook_id}/{timestamp}.pdf` 경로로 업로드하고, 응답에는 1시간짜리 서명 URL만 내려줌(고정 공개 URL 없음).
- `cover_theme`은 `app/services/pdf.py`의 `COVER_THEMES`(mono/lavender/sunset) 중 선택하는 프리셋 방식 — 자유 이미지 업로드는 지원하지 않음.

## 8. Phase 4 구현 범위와 한계

- **통계**: `/stats/overview`로 실제 구현(완결 권수, 진행률, 톤 카테고리 누적 점수).
- **데이터 백업**: `/account/data-export`로 실제 구현(JSON 전체 덤프). 책(PDF) "출판"과는 별개 기능입니다.
- **작성 알림("오늘 아직 안 쓰셨어요")**: 별도 엔드포인트를 새로 만들지 않았습니다. 이미 있는 `/entries/today`로 `today_count`가 0인지 프론트엔드가 확인해 인앱 배너를 띄우면 됩니다. 이메일/푸시처럼 사용자가 앱을 안 열어도 오는 알림은 발송 인프라(이메일 서비스, 스케줄러)가 추가로 필요해서 이번 범위에는 포함하지 않았습니다.
- **생체인증 잠금**: `profiles.app_lock_enabled`와 `PATCH /account/profile`로 on/off 설정값만 백엔드에 저장했습니다. 실제 지문/Face ID 프롬프트는 브라우저의 WebAuthn/플랫폼 생체 API를 쓰는 **프론트엔드 영역**이며, 이 저장소에는 아직 프론트엔드가 없어 그 부분은 구현하지 않았습니다.

## 9. 로컬에서 SQL 스키마만 검증하기 (Docker 없이)

Supabase 프로젝트(특히 다른 앱과 공유 중인 프로젝트)에 바로 마이그레이션을 실행해보기 전에,
`migrations/001_init.sql`의 트리거·RLS 로직만 로컬 PostgreSQL로 먼저 검증할 수 있습니다.
Docker나 Supabase CLI 없이 이 PC에 이미 설치된 PostgreSQL 16을 그대로 쓰되, 시스템에 떠 있는
Postgres 서비스는 건드리지 않고 **완전히 격리된 임시 클러스터**를 하나 새로 띄웁니다.

```bash
PGBIN="/c/Program Files/PostgreSQL/16/bin"

# 1) 테스트 전용 클러스터 생성 (최초 1회)
"$PGBIN/initdb.exe" -D ".localpg/data" -U postgres -A trust -E UTF8 --locale=C
# .localpg/data/postgresql.conf 에서 port = 5432 를 다른 값(예: 54329)으로 바꿔
# 시스템 Postgres 서비스(5432)와 충돌하지 않게 합니다.

# 2) 기동
"$PGBIN/pg_ctl.exe" -D ".localpg/data" -l ".localpg/server.log" start

# 3) auth/storage 스텁 + 실제 마이그레이션 + 권한 적용
export PGPORT=54329 PGUSER=postgres PGHOST=127.0.0.1
"$PGBIN/psql.exe" -d postgres -c "create database silpaejak_test;"
"$PGBIN/psql.exe" -d silpaejak_test -f ".localpg/00_supabase_stub.sql"   # auth.users/auth.uid()/storage 흉내
"$PGBIN/psql.exe" -d silpaejak_test -f "migrations/001_init.sql"
"$PGBIN/psql.exe" -d silpaejak_test -f ".localpg/02_grants.sql"          # authenticated/anon 역할 테이블 권한

# 4) 검증 (하루 5장 제한 / 내용 수정 불가 / RLS 격리까지 확인)
"$PGBIN/psql.exe" -d silpaejak_test -f ".localpg/01_test.sql"

# 5) 끝나면 정지
"$PGBIN/pg_ctl.exe" -D ".localpg/data" stop
```

`.localpg/00_supabase_stub.sql`은 Supabase가 실제로 제공하는 `auth.users`/`auth.uid()`/`storage.objects`/
`storage.foldername()`와 `anon`/`authenticated`/`service_role` 역할을 로컬 테스트에 필요한 만큼만
재현한 것이며, 진짜 Supabase 프로젝트의 Auth/Storage 자체(가입, 로그인, 실제 파일 업로드)를 대신하지는
않습니다. `.localpg/01_test.sql`은 `request.jwt.claim.sub` 세션 변수로 로그인한 사용자를 바꿔가며
① 하루 최대 5장 제한, ② 글 내용 수정 불가, ③ 다른 사용자 데이터 격리(RLS)를 순서대로 검증합니다.

이 로컬 테스트로 **실제로 버그 하나를 찾아 고쳤습니다**: `entries` 테이블의 INSERT/UPDATE RLS 정책이
`user_id`만 확인하고 `notebook_id`가 진짜 그 사용자 소유인지는 확인하지 않아서, 다른 사람의
`notebook_id`를 끼워 넣는 것이 가능했습니다(FastAPI 쪽에서는 notebook_id를 직접 입력받지 않아 막혀
있었지만, Supabase REST API에 직접 요청하면 우회 가능했던 지점). `001_init.sql`의 해당 정책에
`exists (select 1 from notebooks where id = notebook_id and user_id = auth.uid())` 조건을 추가해
막았습니다. haru city 프로젝트에 이미 마이그레이션을 실행했다면, 수정된 `001_init.sql`을 한 번 더
실행해 정책만 갱신하세요(테이블/데이터는 그대로 두고 정책만 drop-then-recreate 하므로 안전합니다).

`.localpg/`는 `.gitignore`에 포함되어 있어 커밋되지 않습니다.

## 10. 아직 하지 않은 것

- 실제 Supabase 프로젝트의 Auth/Storage까지 포함한 end-to-end 테스트(위 로컬 테스트는 SQL 스키마·RLS
  로직만 검증하며, 진짜 가입/로그인/파일 업로드는 다루지 않습니다. 지금까지는 가짜 클라이언트/TestClient와
  이 로컬 PostgreSQL 검증으로 로직만 확인했습니다).
- 프론트엔드(웹) 전체.
