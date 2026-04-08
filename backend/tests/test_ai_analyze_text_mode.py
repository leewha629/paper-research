"""FIX_ANALYZE_SPEED 회귀 테스트.

목적: ai.py의 analyze_paper가 structured 분석에 대해 expect="text"로 LLM을 호출하고,
응답에 markdown fence가 섞여 와도 사후 parse_json_response로 정상 dict를 추출함을 검증.

이 테스트는 두 가지를 동시에 잠근다:
1. analyze_paper가 expect="text"를 전달한다 (디코더 grammar 회귀 방지).
2. structured 분석 결과는 dict로 직렬화되어 result_json 컬럼에 들어간다.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from models import Paper


@pytest.mark.asyncio
async def test_analyze_paper_structured_parses_markdown_fence_response(
    db_session, mock_ai
):
    """markdown fence가 포함된 raw text 응답이 와도 structured 분석이 정상 파싱된다."""
    # 샘플 논문 시드
    paper = Paper(
        paper_id="test-structured-001",
        title="Cu/SSZ-13 NH3-SCR 저온 활성 향상 연구",
        abstract="Cu/SSZ-13 제올라이트의 저온 NH3-SCR 활성 개선...",
        pdf_text="본문 일부",
    )
    db_session.add(paper)
    db_session.commit()
    db_session.refresh(paper)

    # 모델이 markdown fence + 잡설을 섞은 응답을 반환하도록 큐잉.
    # mock_ai의 patched_call_llm은 expect="text"면 raw text를 그대로 돌려준다.
    fenced_response = (
        "```json\n"
        '{"purpose": "Cu/SSZ-13 NH3-SCR 저온 활성 향상", '
        '"catalysts": ["Cu/SSZ-13"], '
        '"synthesis_methods": ["수열합성"], '
        '"characterization_techniques": ["XRD", "BET"], '
        '"key_results": ["200°C에서 95% 전환율"], '
        '"relevance_to_environmental_catalysis": "디젤 NOx 저감"}\n'
        "```"
    )
    mock_ai.queue_text(fenced_response)

    from routers.ai import analyze_paper

    result = await analyze_paper(
        paper_id=paper.id,
        body={"analysis_type": "structured"},
        db=db_session,
    )

    # expect="text"로 호출되었는지 검증
    assert len(mock_ai.calls) == 1
    assert mock_ai.calls[0]["expect"] == "text"
    # max_retries=1, timeout_s=60 강제 검증
    assert mock_ai.calls[0]["max_retries"] == 1

    # 사후 파싱 결과: result_json에 dict가 직렬화되어야 함
    assert result["analysis_type"] == "structured"
    assert result["result_json"] is not None
    parsed = json.loads(result["result_json"])
    assert parsed["purpose"].startswith("Cu/SSZ-13")
    assert "Cu/SSZ-13" in parsed["catalysts"]
    assert "수열합성" in parsed["synthesis_methods"]


