"""Phase A 회귀 테스트 — dashboard `_discovery_running` 1건 (#10).

PLAN §A.2 매핑:
    #10 test_discovery_running_dict_blocks_second_call_same_process
       (현재 동작 캡처: 같은 프로세스 내 중복 호출은 막지만, 멀티 워커 race는
        여전히 존재 = AUDIT §9 #4. Phase E에서 파일락/DB 마커로 교체.)
"""
from __future__ import annotations

import pytest
from fastapi import BackgroundTasks, HTTPException

from routers.dashboard import _discovery_running, trigger_agent_run


# ─── #10 ── (현재 동작 캡처: in-process dict 락) ────────────────────────
@pytest.mark.asyncio
async def test_discovery_running_dict_blocks_second_call_same_process(db_session):
    """**현재 동작 캡처**: `_discovery_running[project] = True`면 같은 프로세스의
    두 번째 trigger_agent_run 호출은 409로 거부된다.

    잠그는 동작: dashboard.py:172-176의 `if _discovery_running.get(project): raise 409`.

    한계 (= 버그): 이는 in-process dict이라 멀티 워커/별도 프로세스 race를
    막지 못한다 (AUDIT §9 #4). Phase E에서 파일락/DB 마커로 교체.
    """
    project = "TEST_PHASE_A"
    # 사전 조건: 기존 상태 청소 (다른 테스트가 남긴 잔재 방어)
    _discovery_running.pop(project, None)
    _discovery_running[project] = True

    try:
        with pytest.raises(HTTPException) as exc_info:
            await trigger_agent_run(
                background_tasks=BackgroundTasks(),
                body={"project": project, "topic": "테스트", "max_candidates": 5},
            )

        assert exc_info.value.status_code == 409
        assert project in str(exc_info.value.detail)
    finally:
        # 다른 테스트에 누수되지 않도록 정리
        _discovery_running.pop(project, None)
