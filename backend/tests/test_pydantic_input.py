"""Phase F-1.5 회귀 테스트 — Pydantic 입력 스키마 검증 3건.

사양 §6 F-1.5:
  #1 빈 name으로 folder 생성 → 422
  #2 잘못된 analysis_type → 422
  #3 정상 입력 → 200/201
"""
from __future__ import annotations

import pytest


# ─── #1 ─────────────────────────────────────────────────────────────────
def test_empty_folder_name_returns_422(client):
    """FolderCreate.name은 min_length=1 — 빈 문자열은 422."""
    resp = client.post("/api/folders", json={"name": ""})
    assert resp.status_code == 422, f"expected 422, got {resp.status_code}: {resp.text}"


# ─── #2 ─────────────────────────────────────────────────────────────────
def test_invalid_analysis_type_returns_422(client):
    """AnalyzeRequest.analysis_type은 Literal — 목록 외 값은 422."""
    # paper_id는 아무 값이나 (404가 아니라 422가 먼저 발생해야 함)
    resp = client.post("/api/ai/analyze/1", json={"analysis_type": "invalid_type_xyz"})
    assert resp.status_code == 422, f"expected 422, got {resp.status_code}: {resp.text}"


# ─── #3 ─────────────────────────────────────────────────────────────────
def test_valid_folder_create_returns_success(client, db_session):
    """유효한 FolderCreate body로 폴더 생성 → 200.

    db_session warm-up: in-memory SQLite는 최초 연결 시 빈 DB를 반환하므로
    HTTP 요청 전에 세션 트랜잭션을 열어 같은 연결(테이블 있는 쪽)을 재사용하게 한다.
    """
    # warm-up: 연결을 열어 test engine의 tables가 있는 연결에 고정.
    from sqlalchemy import text
    db_session.execute(text("SELECT 1"))

    resp = client.post("/api/folders", json={"name": "테스트폴더"})
    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["name"] == "테스트폴더"
    assert "id" in data
