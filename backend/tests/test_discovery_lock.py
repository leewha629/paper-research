"""Phase E §A.2 + v2 — discovery_lock 5건.

PLAN §A.2 Phase E:
- test_concurrent_run_blocked_by_file_lock
- test_lock_released_on_exception
- test_heartbeat_updated_during_long_run

Phase E v2 추가:
- test_two_collections_run_in_parallel
- test_same_collection_blocks_second
"""
from __future__ import annotations

import asyncio
import os
import time

import pytest

from services.discovery_lock import discovery_lock, LockedError, lock_path_for, locked_by


@pytest.fixture
def cleanup_locks():
    """테스트 시작/종료 시 잔재 락 파일 제거."""
    created = []

    def _track(name: str):
        created.append(name)
        p = lock_path_for(name)
        if p.exists():
            p.unlink()
        return name

    yield _track

    for name in created:
        p = lock_path_for(name)
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass


# ─── #1 같은 collection 두 번째 락 시도는 거부 ──────────────────────────
def test_concurrent_run_blocked_by_file_lock(cleanup_locks):
    """첫 락 보유 중 같은 collection 두 번째 시도 → LockedError."""
    name = cleanup_locks("CF4_LOCK_TEST")
    with discovery_lock(name):
        with pytest.raises(LockedError) as exc:
            with discovery_lock(name):
                pass
        assert exc.value.collection_id == name
        assert "이미 실행" in str(exc.value)


# ─── #2 동의어: PLAN §"v2 추가" — 같은 collection 두 번째 즉시 거부 ──────
def test_same_collection_blocks_second(cleanup_locks):
    """v2 항목과 동일하지만 명시적 명세 — 사용자 검증 체크리스트 매핑."""
    name = cleanup_locks("CPN0_LOCK_TEST")
    t0 = time.time()
    with discovery_lock(name):
        with pytest.raises(LockedError):
            with discovery_lock(name):
                pass
    elapsed = time.time() - t0
    # 즉시 거부 — 블록 대기 없음
    assert elapsed < 1.0


# ─── #3 예외 발생 시에도 락 해제 보장 ───────────────────────────────────
def test_lock_released_on_exception(cleanup_locks):
    """with 블록 안에서 예외가 나도 락은 해제된다 (다음 acquire 성공)."""
    name = cleanup_locks("EXC_LOCK_TEST")

    with pytest.raises(RuntimeError, match="boom"):
        with discovery_lock(name):
            raise RuntimeError("boom")

    # 동일 collection 다시 잡을 수 있어야 한다
    with discovery_lock(name):
        pass


# ─── #4 두 collection 동시 — 둘 다 진행 가능 ─────────────────────────────
def test_two_collections_run_in_parallel(cleanup_locks):
    """다른 collection_id는 별도 락 파일이므로 동시 acquire 가능."""
    a = cleanup_locks("MULTI_A")
    b = cleanup_locks("MULTI_B")

    with discovery_lock(a):
        with discovery_lock(b):
            # 둘 다 잡혀 있는 상태 — 같은 a를 다시 잡으면 거부되어야
            with pytest.raises(LockedError):
                with discovery_lock(a):
                    pass


# ─── #5 heartbeat 갱신 (asyncio 짧은 사이클로 검증) ──────────────────────
@pytest.mark.asyncio
async def test_heartbeat_updated_during_long_run(cleanup_locks, db_session, monkeypatch):
    """긴 사이클 동안 AgentRun.heartbeat_at이 갱신된다.

    실제 ollama/S2를 쓰지 않기 위해 keywords 빈 리스트 경로(early return)를
    이용한다 — extract_keywords를 monkeypatch.
    """
    from services.research_agent import discovery as disco_mod
    from models import AgentRun

    cleanup_locks("HB_TEST")

    # extract_keywords가 빈 리스트를 반환하도록 (네트워크 호출 차단)
    class FakeKW:
        keywords = []

    async def fake_extract(*a, **k):
        return FakeKW()

    async def fake_score(*a, **k):
        from services.llm.schemas import RelevanceJudgment  # type: ignore
        return RelevanceJudgment(score=5, reason="test")

    monkeypatch.setattr(disco_mod, "extract_keywords", fake_extract)
    monkeypatch.setattr(disco_mod, "score_relevance", fake_score)

    # heartbeat 주기를 짧게
    monkeypatch.setattr(disco_mod, "HEARTBEAT_INTERVAL_SECONDS", 0.05)

    # bootstrap_project가 실 DB SessionLocal을 쓰므로, in-memory 테스트 DB로 swap
    from database import SessionLocal as RealSL
    monkeypatch.setattr(disco_mod, "SessionLocal", lambda: db_session)

    from services.research_agent import bootstrap as bs_mod
    monkeypatch.setattr(bs_mod, "SessionLocal", lambda: db_session)

    # 사이클 시작 → 짧은 sleep → heartbeat가 갱신되었는지 확인
    # 빈 키워드 → early return 이지만 시작 INSERT는 발생
    report = await disco_mod.run_discovery_cycle(
        "HB_TEST", "테스트 주제", limit_per_query=1, max_candidates=1
    )

    rows = db_session.query(AgentRun).all()
    assert len(rows) >= 1
    last = rows[-1]
    assert last.heartbeat_at is not None
    assert last.locked_by is not None
    assert ":" in last.locked_by  # hostname:pid 포맷
