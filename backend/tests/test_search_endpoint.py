"""Phase C 회귀 테스트 — 검색 엔드포인트 fail-loud (#19).

PLAN §A.2 매핑:
    #19 test_search_returns_503_when_ollama_down

GET /api/search 엔드포인트가 한국어 쿼리를 처리할 때 번역 단계에서 AI가
실패하면 글로벌 LLMError 핸들러가 503을 반환해야 한다 (PLAN §C.1).

NOTE: TestClient/in-memory SQLite 멀티 커넥션 이슈를 피하기 위해 함수
직접 호출 + LLMError raise 검증으로 단순화한다 (글로벌 핸들러 자체는
PHASE_C_DONE의 수동 검증 시나리오에서 확인).
"""
from __future__ import annotations

import pytest

from routers.search import search_papers
from services.llm.exceptions import LLMUpstreamError, LLMError


@pytest.mark.asyncio
async def test_search_returns_503_when_ollama_down(db_session, mock_ai):
    """Phase C: 한국어 쿼리 + AI 다운 → search_papers가 LLMError를 raise.

    글로벌 핸들러(`backend/main.py`)가 이 LLMError를 503 응답으로 변환한다.
    """
    mock_ai.set_default_error(LLMUpstreamError("ollama 11434 connect refused"))

    with pytest.raises(LLMError):
        await search_papers(
            q="이산화탄소 환원 촉매",
            limit=10,
            offset=0,
            year_from=None,
            year_to=None,
            open_access_only=False,
            sort="relevance",
            venues=None,
            fields_of_study=None,
            author=None,
            db=db_session,
        )
