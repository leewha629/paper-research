"""Phase A 회귀 테스트 — parse_json_response 1건 (#4).

원래 #1~#3은 AIClient.complete 자체를 테스트했으나, Phase F-1.4에서
AIClient 삭제 후 제거. parse_json_response는 services.llm.router로 이전.
"""
from __future__ import annotations

from services.llm.router import parse_json_response


# ─── #4 ─────────────────────────────────────────────────────────────────
def test_parse_json_response_strips_markdown_fence():
    """`parse_json_response`는 ```json``` 코드펜스를 벗기고 dict를 반환한다."""
    raw = '```json\n{"score": 7, "reason": "직접 관련"}\n```'
    parsed = parse_json_response(raw)

    assert parsed == {"score": 7, "reason": "직접 관련"}

    # 추가: 배열도 같은 방식으로 처리되는지 확인
    raw_list = '```\n[{"id": 0, "score": 9}, {"id": 1, "score": 2}]\n```'
    parsed_list = parse_json_response(raw_list)
    assert isinstance(parsed_list, list)
    assert parsed_list[0]["id"] == 0
    assert parsed_list[1]["score"] == 2
