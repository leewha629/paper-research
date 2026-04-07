"""Phase A 회귀 테스트 — alerts._score_relevance 2건 (#8~#9).

PLAN §A.2 매핑:
    #8 test_score_relevance_extracts_first_number
    #9 test_score_relevance_returns_5_on_no_match  ← 현재 버그 캡처
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from ai_client import AIClient
from routers.alerts import _score_relevance


def _make_sub() -> SimpleNamespace:
    """Subscription DB 모델 대신 가벼운 stub."""
    return SimpleNamespace(
        sub_type="keyword",
        query="CF4 abatement",
        label="CF4 추적",
    )


def _make_paper() -> dict:
    return {
        "title": "Plasma abatement of CF4",
        "authors": [{"name": "Lee, S."}],
        "year": 2024,
        "venue": "Journal of Hazardous Materials",
        "abstract": "Plasma destruction of CF4 in semiconductor exhaust.",
    }


# ─── #8 ─────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_score_relevance_extracts_first_number(db_session, mock_ai):
    """LLM 응답에서 첫 숫자(정수/소수)를 점수로 추출한다.

    잠그는 동작: alerts.py:283-286의 `re.search(r"(\\d+\\.?\\d*)", ...)`.
    Phase B/C에서 strict_call(schema=RelevanceScore)로 교체될 예정.
    """
    mock_ai.queue_text("8.5 — 매우 관련 있음")

    ai = AIClient(db_session)
    score = await _score_relevance(ai, _make_sub(), _make_paper())

    assert score == 8.5


# ─── #9 ─── (현재 버그 캡처) ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_score_relevance_returns_5_on_no_match(db_session, mock_ai):
    """**현재 버그 캡처**: 응답에 숫자가 전혀 없으면 5.0을 하드코딩 반환.

    이는 AUDIT §9 #2의 "유령 알림" 원흉이다 — AI가 의미 없는 답을 해도
    항상 중간 점수가 박혀 임계값을 통과해버린다.

    잠그는 동작: alerts.py:287의 `return 5.0`.
    Phase C 후속 테스트(#20, #21)는 Alert을 만들지 않거나 별도 실패 레코드를
    기대한다.
    """
    mock_ai.queue_text("관련성을 판단할 수 없습니다")

    ai = AIClient(db_session)
    score = await _score_relevance(ai, _make_sub(), _make_paper())

    assert score == 5.0
