"""
Migration 004: Phase F-1.2 — eval_failed 컬럼 + "평가 실패" 시스템 폴더

추가:
- papers 테이블: is_eval_failed (BOOLEAN DEFAULT 0), eval_failure_reason (TEXT),
  eval_retry_count (INTEGER DEFAULT 0)
- folders: 각 프로젝트 parent 폴더 아래에 "평가 실패" 서브폴더 생성

멱등: 이미 적용된 컬럼/폴더는 skip.
사용자 승인 + dry-run 후 본 DB 적용 (§F-1.2 프로토콜).
"""
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from typing import List, Tuple


COLUMNS_TO_ADD: List[Tuple[str, str, str, str]] = [
    # (table, column, type, default)
    ("papers", "is_eval_failed", "BOOLEAN NOT NULL DEFAULT 0", ""),
    ("papers", "eval_failure_reason", "TEXT", ""),
    ("papers", "eval_retry_count", "INTEGER NOT NULL DEFAULT 0", ""),
]


def column_exists(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def backup_db(db_path: str) -> str:
    backups_dir = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(db_path)), "backups")
    )
    os.makedirs(backups_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backups_dir, f"papers_pre_004_{ts}.db")
    shutil.copy2(db_path, backup_path)
    print(f"💾 백업 생성: {backup_path}")
    return backup_path


def ensure_eval_failed_folders(cur: sqlite3.Cursor) -> int:
    """각 프로젝트 parent 폴더(is_system_folder=1, parent_id IS NULL) 아래에
    '평가 실패' 서브폴더가 없으면 생성."""
    cur.execute(
        "SELECT id, name FROM folders WHERE is_system_folder=1 AND parent_id IS NULL"
    )
    parents = cur.fetchall()
    created = 0
    for parent_id, parent_name in parents:
        cur.execute(
            "SELECT id FROM folders WHERE parent_id=? AND name='평가 실패'",
            (parent_id,),
        )
        if cur.fetchone():
            print(f"⏭  이미 존재: '{parent_name}' → '평가 실패'")
            continue
        cur.execute(
            "INSERT INTO folders (name, parent_id, is_system_folder) VALUES ('평가 실패', ?, 1)",
            (parent_id,),
        )
        print(f"✅ 생성: '{parent_name}' → '평가 실패' (id={cur.lastrowid})")
        created += 1
    return created


def run_migration(db_path: str) -> None:
    if not os.path.exists(db_path):
        print(f"❌ DB 파일을 찾을 수 없음: {db_path}")
        sys.exit(1)

    print(f"📂 DB: {db_path}")
    backup_db(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. 컬럼 추가
    added_cols = 0
    for table, column, type_def, _ in COLUMNS_TO_ADD:
        if column_exists(cur, table, column):
            print(f"⏭  이미 존재: {table}.{column}")
            continue
        sql = f"ALTER TABLE {table} ADD COLUMN {column} {type_def}"
        try:
            cur.execute(sql)
            print(f"✅ 추가: {table}.{column} ({type_def})")
            added_cols += 1
        except sqlite3.OperationalError as e:
            print(f"❌ 실패: {table}.{column} — {e}")

    # 2. "평가 실패" 시스템 폴더 생성
    print()
    print("─── 평가 실패 폴더 ───")
    folders_created = ensure_eval_failed_folders(cur)

    conn.commit()
    conn.close()

    print()
    print(f"📊 컬럼 추가: {added_cols}")
    print(f"📊 폴더 생성: {folders_created}")
    print("✨ Migration 004 완료")


if __name__ == "__main__":
    db_arg = sys.argv[1] if len(sys.argv) > 1 else None
    if db_arg:
        run_migration(db_arg)
    else:
        here = os.path.dirname(os.path.abspath(__file__))
        default_db = os.path.normpath(
            os.path.join(here, "..", "..", "data", "papers.db")
        )
        run_migration(default_db)
