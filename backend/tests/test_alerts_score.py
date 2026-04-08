"""Phase A + Phase C 회귀 테스트 — alerts._score_relevance 및 check_alerts.

PLAN §A.2 매핑:
    #8  test_score_relevance_extracts_first_number  (Phase A — 유지)
    #20 test_check_alerts_skips_when_score_fails    (Phase C — Phase A의 #9 교체)
    #21 test_check_alerts_emits_failure_record_for_ui (Phase C — UI 표면화)

#9 (`test_score_relevance_returns_5_on_no_match`)는 5.0 하드코딩 폴백을
잠그던 특성화 테스트로, Phase C에서 폴백을 제거하면서 #20/#21로 교체된다.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from ai_client import AIClient
from models import Alert, Subscription
from routers.alerts import _score_relevance, check_alerts
from services.llm.exceptions import LLMUpstreamError, LLMSchemaError


def _make_sub() -> SimpleNamespace:
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
    """Phase C 마이그레이션 후: strict_call(schema=RelevanceScore) 경유.

    mock_ai 픽스처는 expect="schema"일 때 큐의 텍스트를 JSON으로 파싱한 뒤
    schema에 검증한다 → queue_text는 RelevanceScore에 맞는 JSON 문자열을
    넣어야 한다.
    """
    mock_ai.queue_text('{"score": 8.5, "reason": "직접 일치"}')

    ai = AIClient(db_session)
    score = await _score_relevance(ai, _make_sub(), _make_paper())

    assert score == 8.5


# ─── #20 ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_check_alerts_skips_when_score_fails(db_session, mock_ai, monkeypatch):
    """Phase C: AI 점수 실패 시 정상 Alert(relevance_score=5.0)는 더 이상
    생성되지 않는다. 대신 is_ai_failed=True 실패 레코드만 생성된다.

    잠그는 동작: 정상 점수 5.0 하드코딩 폴백 제거. AUDIT §9 #2 (유령 알림) 해결.
    """
    # 활성 구독 1건 시드
    sub = Subscription(sub_type="keyword", query="CF4 abatement", label="CF4")
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)

    # S2 mock — 1건의 새 논문 반환
    fake_paper = {
        "paperId": "s2-fake-001",
        "title": "Fake plasma abatement paper",
        "year": 2025,
        "venue": "Mock Journal",
        "authors": [{"name": "Tester"}],
        "abstract": "Test abstract.",
    }

    async def fake_search(self, *args, **kwargs):
        return {"data": [fake_paper]}

    from s2_client import S2Client

    monkeypatch.setattr(S2Client, "search", fake_search)

    # AI 호출은 LLMError로 항상 실패
    mock_ai.set_default_error(LLMUpstreamError("ollama down"))

    # check_alerts 직접 호출 (FastAPI dependency 우회)
    result = await check_alerts(db_session)

    # 새 알림은 1건이지만, relevance_score=5.0인 정상 알림은 0건이어야 한다.
    db_session.commit()
    five_point_alerts = (
        db_session.query(Alert)
        .filter(Alert.subscription_id == sub.id, Alert.relevance_score == 5.0)
        .count()
    )
    assert five_point_alerts == 0, "5.0 하드코딩 폴백이 여전히 살아 있음"


# ─── #21 ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_check_alerts_emits_failure_record_for_ui(
    db_session, mock_ai, monkeypatch
):
    """Phase C: AI 점수 실패는 별도 실패 레코드(is_ai_failed=True)로 저장.

    잠그는 동작:
    - relevance_score = NULL
    - is_ai_failed = True
    - ai_failure_reason 은 enum-like 코드 ("upstream_5xx" / "ollama_down" 등)
    - ai_failure_detail 은 raw 메시지 (디버깅용)
    """
    sub = Subscription(sub_type="keyword", query="CF4 abatement", label="CF4")
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)

    fake_paper = {
        "paperId": "s2-fake-002",
        "title": "Another fake paper",
        "year": 2025,
        "venue": "Mock Journal",
        "authors": [{"name": "Tester"}],
        "abstract": "Test abstract 2.",
    }

    async def fake_search(self, *args, **kwargs):
        return {"data": [fake_paper]}

    from s2_client import S2Client

    monkeypatch.setattr(S2Client, "search", fake_search)

    # Schema 검증 실패로 분류 → reason="schema_invalid"
    mock_ai.set_default_error(LLMSchemaError("invalid score field"))

    await check_alerts(db_session)
    db_session.commit()

    failure_alerts = (
        db_session.query(Alert)
        .filter(Alert.subscription_id == sub.id, Alert.is_ai_failed == True)  # noqa: E712
        .all()
    )
    assert len(failure_alerts) == 1
    fa = failure_alerts[0]
    assert fa.relevance_score is None
    assert fa.is_ai_failed is True
    assert fa.ai_failure_reason == "schema_invalid"
    assert "invalid score field" in (fa.ai_failure_detail or "")
