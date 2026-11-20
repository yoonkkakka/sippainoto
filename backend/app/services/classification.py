"""외부 AI(LLM) API 없이, keyword_dictionary 테이블의 단어/가중치만으로
위기(109) 감지와 감정 톤 점수를 계산하는 자체 구축 분류 로직.
(기획서.md 섹션 2.3, 2.4, 10)
"""

from supabase import Client

HOTLINE_NUMBER = "109"
CRISIS_MESSAGE = (
    "많이 힘든 하루였나 봐요. 24시간 상담 가능한 109(정신건강 위기상담전화)로 연결해드릴까요?"
)

TONE_CATEGORIES = [
    "tone_depression",
    "tone_helplessness",
    "tone_self_deprecation",
    "tone_anger",
]

# 하루 사용자 데이터가 쌓이기 전까지의 잠정 임계값. 실제 운영 데이터로 보정 필요.
EMOTION_SCORE_THRESHOLD = 15.0


def _fetch_active_terms(client: Client, categories: list[str]) -> list[dict]:
    result = (
        client.table("keyword_dictionary")
        .select("term, category, weight")
        .in_("category", categories)
        .eq("is_active", True)
        .execute()
    )
    return result.data or []


def check_crisis(client: Client, content: str) -> bool:
    """109 위기 감지: 고위험 키워드가 하나라도 포함되면 즉시(동기) true.
    비동기 톤 점수와 달리 생명과 직결되는 영역이라 저장 시점에 바로 체크한다."""
    terms = _fetch_active_terms(client, ["crisis"])
    lowered = content.lower()
    return any(t["term"].lower() in lowered for t in terms)


def compute_tone_scores(client: Client, content: str) -> dict[str, float]:
    """글 전체의 '어두운 톤 점수'를 카테고리별로 계산.
    단어 하나의 존재 여부가 아니라, 등장 빈도 × 가중치를 글자 수로 정규화한
    밀도(1,000자당)로 점수화한다."""
    terms = _fetch_active_terms(client, TONE_CATEGORIES)
    scores: dict[str, float] = {category: 0.0 for category in TONE_CATEGORIES}

    length = max(len(content), 1)
    lowered = content.lower()
    for term in terms:
        word = term["term"].lower()
        occurrences = lowered.count(word)
        if occurrences:
            density = occurrences * float(term["weight"]) / length * 1000
            scores[term["category"]] += density

    return {category: round(score, 2) for category, score in scores.items()}


def total_dark_score(scores: dict[str, float]) -> float:
    return sum(scores.values())


def reclassify_entry_tone(client: Client, entry_id: str, user_id: str) -> None:
    """저장 후 비동기(백그라운드)로 실행되는 톤 점수 재판단.
    수동 태그 여부와 무관하게 항상 점수를 계산해 기록하고,
    아직 '실패작' 노트에 있는 글이 임계값을 넘으면 '감정' 노트로 이동시킨다.
    (이미 감정 노트에 있는 글은 더 옮기지 않음 — 자동 점수로 '되돌리기'는 하지 않음)"""
    # 순환 참조를 피하기 위해 함수 내부에서 import.
    from app.services.notebooks import complete_notebook_if_full, get_or_create_current_notebook

    entry_result = (
        client.table("entries")
        .select("id, content, notebook_id, notebooks(type)")
        .eq("id", entry_id)
        .single()
        .execute()
    )
    entry = entry_result.data
    if not entry:
        return

    scores = compute_tone_scores(client, entry["content"])
    client.table("entries").update({"tone_scores": scores}).eq("id", entry_id).execute()

    current_type = entry["notebooks"]["type"]
    if current_type == "emotion":
        return

    if total_dark_score(scores) >= EMOTION_SCORE_THRESHOLD:
        target_notebook = get_or_create_current_notebook(client, user_id, "emotion")
        client.table("entries").update({"notebook_id": target_notebook["id"]}).eq("id", entry_id).execute()
        complete_notebook_if_full(client, target_notebook)
