"""Phase A 회귀 테스트 — `AIClient.complete` 4건 (#1~#4).

PLAN §A.2 매핑:
    #1 test_complete_returns_text_when_expect_json_false
    #2 test_complete_retries_on_invalid_json_when_expect_json_true
    #3 test_complete_returns_raw_text_after_max_retries  ← 현재 버그 캡처
    #4 test_parse_json_response_strips_markdown_fence

이 파일은 `AIClient.complete` 자체의 동작을 검증하므로 mock_ai (고수준)가
아니라 mock_ollama_lowlevel (저수준)을 사용한다 — retry/JSON 검증 로직이
실제로 돌아야 한다.
"""
from __future__ import annotations

import pytest

from ai_client import AIClient, parse_json_response


# ─── #1 ─────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_complete_returns_text_when_expect_json_false(
    db_session, mock_ollama_lowlevel
):
    """expect_json=False면 응답 텍스트가 그대로 반환된다.

    잠그는 동작: 평문 모드에서 JSON 검증 분기를 타지 않음.
    """
    mock_ollama_lowlevel(["plain text response"])
    ai = AIClient(db_session)

    text, backend, model = await ai.complete(
        system="sys", user="usr", expect_json=False
    )

    assert text == "plain text response"
    assert backend == "ollama"
    assert model == "mock-model"


# ─── #2 ─────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_complete_retries_on_invalid_json_when_expect_json_true(
    db_session, mock_ollama_lowlevel
):
    """expect_json=True일 때 잘못된 JSON이 오면 재시도하고, 다음 응답이
    유효 JSON이면 그것을 반환한다.

    잠그는 동작: JSONDecodeError → continue → 두 번째 호출 성공 시 정상 반환.
    """
    state = mock_ollama_lowlevel(
        [
            "this is not json at all",  # 1차: 실패
            '{"score": 8}',              # 2차: 성공
        ]
    )
    ai = AIClient(db_session)

    text, _, _ = await ai.complete(
        system="sys", user="usr", expect_json=True, max_retries=2
    )

    assert text == '{"score": 8}'
    assert state["calls"] == 2  # 정확히 2회 호출


# ─── #3 ─── (현재 버그 캡처) ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_complete_returns_raw_text_after_max_retries(
    db_session, mock_ollama_lowlevel
):
    """**현재 버그 캡처**: 모든 재시도가 invalid JSON이어도 raise하지 않고
    마지막 raw 텍스트를 그대로 반환한다.

    PLAN §"Phase A에서 작성 (10건)" #3 — Phase B의 strict_call이 이 동작을
    제거할 예정. 그때 이 테스트는 의도적으로 깨지고 fail-loud 버전으로 교체.

    잠그는 동작: ai_client.py:54-55의 `return result, be, model` 폴백 경로.
    """
    invalid = "still not json"
    state = mock_ollama_lowlevel([invalid, invalid, invalid])
    ai = AIClient(db_session)

    text, backend, model = await ai.complete(
        system="sys", user="usr", expect_json=True, max_retries=2
    )

    # 버그: raise하지 않고 마지막 raw 텍스트가 반환됨
    assert text == invalid
    assert backend == "ollama"
    assert state["calls"] == 3  # max_retries=2 → 총 3회 (0,1,2)


# ─── #4 ─────────────────────────────────────────────────────────────────
def test_parse_json_response_strips_markdown_fence():
    """`parse_json_response`는 ```json``` 코드펜스를 벗기고 dict를 반환한다.

    잠그는 동작: ai_client.py:144-156의 마크다운 코드블록 제거 정규식.
    """
    raw = '```json\n{"score": 7, "reason": "직접 관련"}\n```'
    parsed = parse_json_response(raw)

    assert parsed == {"score": 7, "reason": "직접 관련"}

    # 추가: 배열도 같은 방식으로 처리되는지 확인
    raw_list = '```\n[{"id": 0, "score": 9}, {"id": 1, "score": 2}]\n```'
    parsed_list = parse_json_response(raw_list)
    assert isinstance(parsed_list, list)
    assert parsed_list[0]["id"] == 0
    assert parsed_list[1]["score"] == 2
