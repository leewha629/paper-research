"""Phase A 회귀 테스트 — search.py 헬퍼 3건 (#5~#7).

PLAN §A.2 매핑 (모두 **현재 폴백 동작 캡처** = 버그 잠금):
    #5 test_translate_korean_returns_original_on_exception
    #6 test_expand_keywords_returns_single_keyword_on_exception
    #7 test_ai_score_papers_returns_all_as_high_on_exception

이 테스트들은 Phase C에서 fail-loud(raise) 버전으로 교체될 예정이다.
"""
from __future__ import annotations

import pytest

from routers.search import (
    ai_score_papers,
    generate_queries_and_terms,
    translate_korean_to_english,
)


# ─── #5 ─── (현재 폴백 캡처) ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_translate_korean_returns_original_on_exception(db_session, mock_ai):
    """**현재 폴백 캡처**: AI 실패 시 원문 한글이 영문 번역 자리에도 그대로
    들어간다 → 사용자는 번역 실패를 모른 채 한글로 S2를 검색하게 됨.

    잠그는 동작: search.py:79-83의 `try/except: return text, text`.
    Phase C 후속 테스트(#16)는 LLMError raise를 기대한다.
    """
    mock_ai.set_default_error(RuntimeError("ollama unavailable"))

    translated, original = await translate_korean_to_english(
        "이산화탄소 환원 촉매", db_session
    )

    # 버그: 영문 자리에 한글 원문이 들어감
    assert translated == "이산화탄소 환원 촉매"
    assert original == "이산화탄소 환원 촉매"
    assert len(mock_ai.calls) == 1


# ─── #6 ─── (현재 폴백 캡처) ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_expand_keywords_returns_single_keyword_on_exception(
    db_session, mock_ai
):
    """**현재 폴백 캡처**: AI 쿼리 확장 실패 시 입력 키워드 하나만 담은
    리스트를 반환 → 검색 범위가 1개 쿼리로 급감하지만 사용자는 모름.

    잠그는 동작: search.py:372-375의 `except: pass; return [keywords], [], ""`.
    Phase C 후속 테스트(#17)는 503 또는 명시적 warning을 기대한다.
    """
    mock_ai.set_default_error(RuntimeError("ollama timeout"))

    queries, terms, expanded = await generate_queries_and_terms(
        "CF4 abatement", db_session, num_queries=6
    )

    assert queries == ["CF4 abatement"]
    assert terms == []
    assert expanded == ""


# ─── #7 ─── (현재 폴백 캡처) ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_ai_score_papers_returns_all_as_high_on_exception(
    db_session, mock_ai
):
    """**현재 폴백 캡처**: AI 점수 매기기 실패 시 모든 논문을 첫 번째 반환값
    (high_relevance) 자리에 그대로 넣고 relevance_score=None으로 둔다.

    이는 RELEVANCE_THRESHOLD 필터링을 사실상 우회시킨다 → AUDIT §9 #1.
    잠그는 동작: search.py:440-445의 `except: ... return papers, []`.
    Phase C 후속 테스트(#18, #19)는 503을 기대한다.
    """
    mock_ai.set_default_error(RuntimeError("ollama down"))

    papers_in = [
        {"paperId": "p1", "title": "Random paper 1", "abstract": "abc"},
        {"paperId": "p2", "title": "Random paper 2", "abstract": "def"},
        {"paperId": "p3", "title": "Random paper 3", "abstract": "ghi"},
    ]

    high, low = await ai_score_papers(papers_in, "CF4 abatement", db_session)

    # 버그 #1: 전체가 high에 들어감 (임계값 우회)
    assert len(high) == 3
    assert low == []
    # 버그 #2: relevance_score가 None이지만 결과에 포함됨
    for p in high:
        assert p["relevance_score"] is None
        assert p["relevance_reason"] is None
