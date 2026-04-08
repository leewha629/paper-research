"""Phase E v2 — migration 003 cleanup 1건.

PLAN v2 추가:
- test_paper_99_cleaned_up

raw sqlite3로 임시 DB를 만들어 paper 99 dup 시나리오를 재현하고,
migration 003 실행 후 dup이 사라지는지 확인.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest


# 마이그레이션 모듈 직접 import
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
sys.path.insert(0, str(MIGRATIONS_DIR))

import importlib.util
spec = importlib.util.spec_from_file_location(
    "mig003",
    MIGRATIONS_DIR / "003_phase_e_lock_heartbeat_unique.py",
)
mig003 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mig003)


def _make_legacy_db(path: str) -> None:
    """Migration 001 후 상태를 흉내 — agent_runs / folder_papers / folders 필요."""
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_system_folder INTEGER DEFAULT 0
        );
        CREATE TABLE folder_papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folder_id INTEGER NOT NULL,
            paper_id INTEGER NOT NULL
        );
        CREATE TABLE agent_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TIMESTAMP NOT NULL
        );
        """
    )
    # paper 99 사고 재현: 같은 paper_id가 두 폴더에 동시 존재
    cur.execute("INSERT INTO folders (id, name, parent_id) VALUES (1, '자동 발견', NULL)")
    cur.execute("INSERT INTO folders (id, name, parent_id) VALUES (2, '풀분석 추천', NULL)")
    cur.execute("INSERT INTO folder_papers (folder_id, paper_id) VALUES (1, 99)")
    cur.execute("INSERT INTO folder_papers (folder_id, paper_id) VALUES (2, 99)")
    # 정상 single mapping도 하나
    cur.execute("INSERT INTO folder_papers (folder_id, paper_id) VALUES (1, 100)")
    conn.commit()
    conn.close()


def test_paper_99_cleaned_up(tmp_path):
    db_path = str(tmp_path / "papers.db")
    _make_legacy_db(db_path)

    # 백업 디렉토리도 tmp 안에
    mig003.run_migration(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1) paper 99의 dup이 사라졌다 — 1개만 남음
    cur.execute("SELECT COUNT(*) FROM folder_papers WHERE paper_id=99")
    assert cur.fetchone()[0] == 1

    # 2) 정상 paper 100은 그대로
    cur.execute("SELECT COUNT(*) FROM folder_papers WHERE paper_id=100")
    assert cur.fetchone()[0] == 1

    # 3) heartbeat_at, locked_by 컬럼이 추가됨
    cur.execute("PRAGMA table_info(agent_runs)")
    cols = {row[1] for row in cur.fetchall()}
    assert "heartbeat_at" in cols
    assert "locked_by" in cols

    # 4) UNIQUE INDEX (folder_id, paper_id) 가 존재
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='uq_folder_papers_folder_paper'"
    )
    assert cur.fetchone() is not None

    # 5) 백업 파일이 생성되었다 (data/backups/papers_pre_003_*.db)
    backups_dir = Path(db_path).parent / "backups"
    assert backups_dir.exists()
    backups = list(backups_dir.glob("papers_pre_003_*.db"))
    assert len(backups) >= 1

    conn.close()
