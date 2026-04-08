"""
Migration 002: Phase C — Alert AI 실패 표면화 컬럼 추가

추가되는 것:
- alerts 테이블 컬럼:
    is_ai_failed       INTEGER NOT NULL DEFAULT 0   (BOOLEAN, 인덱스)
    ai_failure_reason  TEXT                          (enum-like 짧은 코드)
    ai_failure_detail  TEXT                          (raw 메시지)

특징:
- 멱등 (이미 적용된 컬럼은 skip)
- DB 적용 전 자동 백업 → data/backups/papers_<timestamp>_pre002.db
- 직접 실행 가능: `python backend/migrations/002_alert_failure.py [db_path]`

배경:
- Phase C — 사일런트 폴백 제거. AI 점수 매기기가 실패하면 5.0을 하드코딩하던
  기존 동작을 제거하고, 별도 실패 레코드(is_ai_failed=True)로 저장한다.
- ai_failure_reason은 GROUP BY 집계용 짧은 enum 코드:
    "timeout" | "schema_invalid" | "upstream_5xx" | "ollama_down" | "unknown"
- ai_failure_detail은 디버깅용 raw 메시지 (최대 500자).
"""
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from typing import List, Tuple


COLUMNS_TO_ADD: List[Tuple[str, str, str]] = [
    ("alerts", "is_ai_failed", "INTEGER NOT NULL DEFAULT 0"),
    ("alerts", "ai_failure_reason", "TEXT"),
    ("alerts", "ai_failure_detail", "TEXT"),
]

INDEXES_TO_CREATE: List[Tuple[str, str]] = [
    (
        "idx_alerts_is_ai_failed",
        "CREATE INDEX idx_alerts_is_ai_failed ON alerts(is_ai_failed)",
    ),
]


def column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def table_exists(cursor: sqlite3.Cursor, table: str) -> bool:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cursor.fetchone() is not None


def index_exists(cursor: sqlite3.Cursor, index_name: str) -> bool:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=?", (index_name,)
    )
    return cursor.fetchone() is not None


def backup_db(db_path: str) -> str:
    backups_dir = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(db_path)), "backups")
    )
    os.makedirs(backups_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backups_dir, f"papers_{ts}_pre002.db")
    shutil.copy2(db_path, backup_path)
    print(f"💾 백업 생성: {backup_path}")
    return backup_path


def run_migration(db_path: str) -> None:
    if not os.path.exists(db_path):
        print(f"❌ DB 파일을 찾을 수 없음: {db_path}")
        sys.exit(1)

    print(f"📂 DB: {db_path}")
    backup_db(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    if not table_exists(cur, "alerts"):
        print("⚠️  alerts 테이블이 없음. 앱을 한 번 실행해 테이블 생성 후 재시도.")
        conn.close()
        sys.exit(2)

    added_cols = 0
    skipped_cols = 0
    added_indexes = 0
    skipped_indexes = 0

    for table, column, type_def in COLUMNS_TO_ADD:
        if column_exists(cur, table, column):
            print(f"⏭  이미 존재: {table}.{column}")
            skipped_cols += 1
            continue
        sql = f"ALTER TABLE {table} ADD COLUMN {column} {type_def}"
        try:
            cur.execute(sql)
            print(f"✅ 추가: {table}.{column} ({type_def})")
            added_cols += 1
        except sqlite3.OperationalError as e:
            print(f"❌ 실패: {table}.{column} — {e}")

    for idx_name, create_sql in INDEXES_TO_CREATE:
        if index_exists(cur, idx_name):
            print(f"⏭  이미 존재: INDEX {idx_name}")
            skipped_indexes += 1
            continue
        try:
            cur.execute(create_sql)
            print(f"✅ 추가: INDEX {idx_name}")
            added_indexes += 1
        except sqlite3.OperationalError as e:
            print(f"❌ 실패: INDEX {idx_name} — {e}")

    conn.commit()
    conn.close()

    print()
    print(f"📊 컬럼: 추가 {added_cols} / 건너뜀 {skipped_cols}")
    print(f"📊 인덱스: 추가 {added_indexes} / 건너뜀 {skipped_indexes}")
    print("✨ Migration 002 완료")


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
