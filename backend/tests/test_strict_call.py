"""Phase B 신규 회귀 테스트 — strict_call 동작 검증 5건 (#11~#15).

PLAN §A.2 매핑:
    #11 test_raises_on_timeout
    #12 test_raises_on_schema_validation_failure
    #13 test_retries_with_exponential_backoff
    #14 test_returns_validated_dict_on_success
    #15 test_legacy_ai_client_complete_delegates_to_strict_call

이 테스트들은 strict_call의 핵심 계약을 잠근다:
    - 실패 시 절대 폴백 반환 없이 LLMError 하위를 raise
    - schema 검증 실패는 retry 후 LLMSchemaError
    - 성공 시 검증된 객체/dict 반환
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from pydantic import BaseModel, Field

from services.llm import strict_call
from services.llm.exceptions import (
    LLMError,
    LLMSchemaError,
    LLMTimeoutError,
)
from services.llm import ollama_client


class _Score(BaseModel):
    score: int = Field(..., ge=0, le=10)
    reason: str = Field(..., min_length=1)


def _patch_ollama_chat(monkeypatch, fake):
    """services.llm.ollama_client._ollama_chat을 monkeypatch."""
    monkeypatch.setattr(ollama_client, "_ollama_chat", fake)


# ─── #11 ────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_raises_on_timeout(monkeypatch):
    """매 시도가 httpx.TimeoutException을 던지면 strict_call은 LLMTimeoutError를 raise.

    잠그는 동작: PLAN §B.1 "실패는 항상 raise. 폴백 반환 없음."
    """

    async def fake(**kwargs):
        raise httpx.TimeoutException("simulated timeout")

    _patch_ollama_chat(monkeypatch, fake)

    with pytest.raises(LLMTimeoutError) as exc:
        await strict_call(
            system="s",
            user="u",
            expect="schema",
            schema=_Score,
            max_retries=1,  # 총 2회 시도
            timeout_s=1.0,
        )
    # LLMError 계층 일부여야 함
    assert isinstance(exc.value, LLMError)


# ─── #12 ────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_raises_on_schema_validation_failure(monkeypatch):
    """모든 시도에서 invalid JSON(또는 검증 실패)이 오면 LLMSchemaError raise.

    잠그는 동작: max_retries 다 써도 검증 통과 못하면 raise (폴백 금지).
    """

    async def fake(**kwargs):
        # JSON 파싱은 되지만 schema(score 0~10, reason 비어있음)에 실패하는 응답
        return '{"score": 999, "reason": ""}'

    _patch_ollama_chat(monkeypatch, fake)

    with pytest.raises(LLMSchemaError):
        await strict_call(
            system="s",
            user="u",
            expect="schema",
            schema=_Score,
            max_retries=2,
        )


# ─── #13 ────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_retries_with_exponential_backoff(monkeypatch):
    """첫 두 시도 실패 → 세 번째 성공이면 strict_call은 성공 결과를 반환.

    "exponential backoff"라는 이름은 PLAN의 명명을 따른 것일 뿐, 실제로는 시도 간
    temperature 사다리 (0.1 → 0.05 → 0.0)로 결정성을 점점 높인다. 핵심은
    "여러 번 재시도하고 마침내 성공하면 정상 반환"이다.
    """
    state = {"calls": 0, "temps": []}

    async def fake(**kwargs):
        state["calls"] += 1
        state["temps"].append(kwargs["temperature"])
        if state["calls"] < 3:
            return "not json at all"  # 1, 2회차 실패
        return '{"score": 7, "reason": "matches topic"}'  # 3회차 성공

    _patch_ollama_chat(monkeypatch, fake)

    result = await strict_call(
        system="s",
        user="u",
        expect="schema",
        schema=_Score,
        max_retries=2,  # 총 3회 시도 허용
    )

    assert isinstance(result, _Score)
    assert result.score == 7
    assert state["calls"] == 3
    # temperature가 시도마다 단조 비증가 (0.1, 0.05, 0.0)
    assert state["temps"] == sorted(state["temps"], reverse=True)


# ─── #14 ────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_returns_validated_dict_on_success(monkeypatch):
    """expect="json" 모드는 dict를 반환하고 schema 검증은 skip한다."""

    async def fake(**kwargs):
        return '{"foo": "bar", "n": 42}'

    _patch_ollama_chat(monkeypatch, fake)

    result = await strict_call(
        system="s",
        user="u",
        expect="json",
        max_retries=0,
    )
    assert isinstance(result, dict)
    assert result == {"foo": "bar", "n": 42}
