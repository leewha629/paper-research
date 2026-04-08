"""Phase C 회귀 테스트 — search.py 헬퍼 fail-loud 동작 (#16, #17, #18).

PLAN §A.2 매핑 (Phase A의 #5, #6, #7을 교체):
    #16 test_translate_raises_when_ai_fails    (Phase A의 #5와 교체)
    #17 test_expand_keywords_raises_when_ai_fails (Phase A의 #6과 교체)
    #18 test_ai_score_papers_raises_when_ai_fails (Phase A의 #7과 교체)

이 테스트들은 Phase C에서 사일런트 폴백을 제거한 후의 동작을 잠근다 — 즉
AI 실패는 절대 조용히 무시되지 않고 항상 LLMError 계열로 raise된다.
"""
from __future__ import annotations

import pytest

from routers.search import (
    ai_score_papers,
    generate_queries_and_terms,
    translate_korean_to_english,
)
from services.llm.exceptions import LLMError


# ─── #16 ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_translate_raises_when_ai_fails(db_session, mock_ai):
    """Phase C: 번역 AI 실패는 그대로 호출자에게 전파된다.

    잠그는 동작: search.py의 try/except 폴백이 제거되어 LLMError 또는 raw
    Exception이 그대로 raise. GET /search 핸들러는 글로벌 LLMError 핸들러를
    통해 503으로 응답.
    """
    mock_ai.set_default_error(LLMError("ollama unavailable"))

    with pytest.raises(LLMError):
        await translate_korean_to_english("이산화탄소 환원 촉매", db_session)

    assert len(mock_ai.calls) == 1


# ─── #17 ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_expand_keywords_raises_when_ai_fails(db_session, mock_ai):
    """Phase C: 쿼리 확장 AI 실패는 그대로 raise.

    상위 호출자(SSE generate)는 이를 catch하여 warning 이벤트로 강등하지만,
    헬퍼 자체는 폴백을 제공하지 않는다 — 사일런트 단일-키워드 폴백 금지.
    """
    mock_ai.set_default_error(LLMError("ollama timeout"))

    with pytest.raises(LLMError):
        await generate_queries_and_terms(
            "CF4 abatement", db_session, num_queries=6
        )


# ─── #18 ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_ai_score_papers_raises_when_ai_fails(db_session, mock_ai):
    """Phase C: AI 점수 매기기 실패는 그대로 raise.

    잠그는 동작: 더 이상 모든 논문을 high 버킷에 임의로 넣지 않는다.
    AUDIT §9 #1 ("RELEVANCE_THRESHOLD 우회") 해결.
    """
    mock_ai.set_default_error(LLMError("ollama down"))

    papers_in = [
        {"paperId": "p1", "title": "Random paper 1", "abstract": "abc"},
        {"paperId": "p2", "title": "Random paper 2", "abstract": "def"},
        {"paperId": "p3", "title": "Random paper 3", "abstract": "ghi"},
    ]

    with pytest.raises(LLMError):
        await ai_score_papers(papers_in, "CF4 abatement", db_session)
