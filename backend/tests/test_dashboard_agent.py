"""Phase E 갱신 — dashboard agent 락 동작 (#10).

이전 Phase A: in-process `_discovery_running` dict 검증 (이미 제거됨).
Phase E §1: collection별 fcntl 파일 락으로 교체. 같은 collection 두 번째
trigger_agent_run 호출은 즉시 409.
"""
from __future__ import annotations

import pytest
from fastapi import BackgroundTasks, HTTPException

from routers.dashboard import trigger_agent_run
from services.discovery_lock import discovery_lock, lock_path_for


@pytest.mark.asyncio
async def test_trigger_agent_run_blocked_when_lock_held(db_session, monkeypatch):
    """락 파일이 잡혀 있으면 trigger_agent_run은 즉시 409."""
    project = "TEST_PHASE_E_DASH"
    # 잔재 정리
    lp = lock_path_for(project)
    if lp.exists():
        lp.unlink()

    with discovery_lock(project):
        with pytest.raises(HTTPException) as exc_info:
            await trigger_agent_run(
                background_tasks=BackgroundTasks(),
                body={"project": project, "topic": "테스트", "max_candidates": 5},
            )
        assert exc_info.value.status_code == 409
        assert project in str(exc_info.value.detail)
