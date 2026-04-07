"""S2Client mock 헬퍼.

PLAN §A.1 — `S2Client.bulk_search` 응답 고정.

monkeypatch로만 동작 → 실제 Semantic Scholar 네트워크 호출 없음.
Phase A 10건 테스트는 직접적으로 S2를 부르지 않지만, 향후 검색 엔드포인트
계약 테스트(#19 등 Phase C 추가분) 준비를 위해 미리 헬퍼만 만든다.
"""
from __future__ import annotations

from typing import Any


def install_mock_s2(monkeypatch, papers: list[dict] | None = None) -> dict:
    """`S2Client.bulk_search`를 고정 응답으로 교체한다.

    papers: 반환할 논문 dict 리스트. None이면 빈 리스트.
    반환되는 state로 호출 횟수와 마지막 인자를 검사할 수 있다.
    """
    state: dict[str, Any] = {"calls": 0, "last_args": None, "papers": papers or []}

    from s2_client import S2Client

    async def patched_bulk_search(self, *args, **kwargs):
        state["calls"] += 1
        state["last_args"] = {"args": args, "kwargs": kwargs}
        return list(state["papers"])

    monkeypatch.setattr(S2Client, "bulk_search", patched_bulk_search, raising=False)
    return state
