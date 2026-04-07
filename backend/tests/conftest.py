"""Phase A 회귀 테스트 conftest.

PLAN §A.1 — DB 픽스처(SQLite in-memory), client 픽스처, mock_ollama 픽스처.
PLAN §"멀티 프로젝트 고려" — db_session 픽스처는 `project_id`를 받을 수 있는
형태로 설계 (Phase A에서는 메타데이터로만 보관, 실제 격리 검증은 Phase E).

중요: 실제 ollama / Semantic Scholar 네트워크는 절대 호출되지 않는다.
mock_ai / mock_s2 픽스처가 monkeypatch로 차단한다.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterator

import pytest

# ─── sys.path 셋업 ─────────────────────────────────────────────────────
# pytest를 어디서 실행하든 backend/ 가 import 경로에 들어오도록 보장.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# ─── DB 픽스처 인프라 ──────────────────────────────────────────────────
# 실제 data/papers.db를 건드리지 않기 위해 in-memory SQLite 엔진을 별도로 만든다.
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import database  # noqa: E402  (sys.path 셋업 후 import)
from database import Base  # noqa: E402
import models  # noqa: F401,E402  (모든 테이블이 Base.metadata에 등록되어야 함)

_TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
)
_TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_TEST_ENGINE)


def _seed_default_settings(session) -> None:
    """AIClient가 동작하려면 ai_backend / ollama_* 키가 있어야 한다."""
    from models import AppSetting

    defaults = {
        "ai_backend": "ollama",  # claude_api_key가 없어도 분기 통과
        "ollama_base_url": "http://localhost:11434",
        "ollama_model": "test-model",
    }
    for k, v in defaults.items():
        session.add(AppSetting(key=k, value=v))
    session.commit()


@pytest.fixture
def db_session(request) -> Iterator:
    """In-memory SQLite 세션.

    멀티 프로젝트 격리 (PLAN §"멀티 프로젝트 고려"):
        @pytest.mark.parametrize("db_session", ["CF4", "CPN"], indirect=True)
        def test_xxx(db_session): ...

    Phase A에서는 project_id를 `session.info["project_id"]`에만 보관한다.
    실제 격리(별도 스키마/별도 DB)는 Phase E에서 추가.
    """
    project_id = getattr(request, "param", "default")

    Base.metadata.create_all(bind=_TEST_ENGINE)
    session = _TestSessionLocal()
    session.info["project_id"] = project_id

    _seed_default_settings(session)

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=_TEST_ENGINE)


@pytest.fixture
def client(db_session, monkeypatch):
    """FastAPI TestClient (필요한 테스트만 사용).

    Phase A의 10건 테스트는 대부분 함수를 직접 호출하므로 실제로 쓰는 곳은 없다.
    Phase C 이후 검색 엔드포인트 503 테스트에서 사용 예정.
    """
    from fastapi.testclient import TestClient
    from main import app
    from database import get_db

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


# ─── 네트워크 차단 가드 (autouse) ───────────────────────────────────────
# PLAN §A.3 — "mock_ai 픽스처가 실제 ollama/s2를 호출하지 않는 것을 확인".
# httpx.AsyncClient.send를 강제로 raise시켜, 만에 하나 mock이 새도 실제
# 네트워크에는 절대 닿지 않도록 보장한다. ssl 모듈을 망가뜨리는
# socket 전역 차단보다 안전하다.
@pytest.fixture(autouse=True)
def _block_real_http(monkeypatch):
    import httpx

    async def _blocked_send(self, *args, **kwargs):
        raise RuntimeError(
            "테스트 중 실제 HTTP 호출 차단됨. mock_ai/mock_s2 픽스처를 사용하세요."
        )

    monkeypatch.setattr(httpx.AsyncClient, "send", _blocked_send)


# ─── Mock 픽스처 (네트워크 차단의 핵심) ─────────────────────────────────
@pytest.fixture
def mock_ai(monkeypatch):
    """`AIClient.complete`를 monkeypatch로 교체.

    PLAN §A.3: mock_ai 픽스처는 monkeypatch로만 동작 → 실제 ollama 호출 0건.
    """
    from tests.fixtures.mock_ai import install_mock_ai

    return install_mock_ai(monkeypatch)


@pytest.fixture
def mock_ollama_lowlevel(monkeypatch):
    """`AIClient._ollama` 저수준 교체용 팩토리.

    test_ai_client_contract.py에서 retry/JSON 검증 로직 자체를 테스트할 때 사용.
    fixture는 install 함수를 그대로 반환한다 (호출자가 응답 리스트를 결정).
    """
    from tests.fixtures.mock_ai import install_mock_ollama

    def _factory(responses: list):
        return install_mock_ollama(monkeypatch, responses)

    return _factory


@pytest.fixture
def mock_s2(monkeypatch):
    """`S2Client.bulk_search` monkeypatch."""
    from tests.fixtures.mock_s2 import install_mock_s2

    def _factory(papers: list[dict] | None = None):
        return install_mock_s2(monkeypatch, papers)

    return _factory


@pytest.fixture
def sample_papers():
    """정적 샘플 논문 10건 (CF4/halogen/VOC 5 + 무관 5)."""
    from tests.fixtures.sample_papers import SAMPLE_PAPERS

    # 테스트가 mutable 변경하지 않도록 복사본 반환
    return [dict(p) for p in SAMPLE_PAPERS]
