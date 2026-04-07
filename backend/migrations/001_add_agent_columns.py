"""
Migration 001: 자율 연구 에이전트용 컬럼/테이블 추가

추가되는 것:
- papers 테이블 컬럼:
    discovered_by, relevance_score, relevance_reason, relevance_checked_at,
    auto_summary, is_trashed, trashed_at, trash_reason
- folders 테이블 컬럼:
    is_system_folder
- 신규 테이블:
    agent_runs        (사이클별 실행 감사 로그)
    searched_keywords (키워드 쿨타임 추적)

특징:
- 멱등 (이미 적용된 컬럼/테이블은 skip)
- 직접 실행 가능: `python backend/migrations/001_add_agent_columns.py [db_path]`
- 인자 없으면 기본 data/papers.db 사용

사용 예:
    python backend/migrations/001_add_agent_columns.py
    python backend/migrations/001_add_agent_columns.py data/papers.db
"""
import os
import sqlite3
import sys
from typing import List, Tuple


# 추가할 컬럼: (테이블명, 컬럼명, SQL 타입+제약)
COLUMNS_TO_ADD: List[Tuple[str, str, str]] = [
    # papers 신규 컬럼
    ("papers", "discovered_by", "TEXT DEFAULT 'manual'"),
    ("papers", "relevance_score", "INTEGER"),
    ("papers", "relevance_reason", "TEXT"),
    ("papers", "relevance_checked_at", "TIMESTAMP"),
    ("papers", "auto_summary", "TEXT"),
    ("papers", "is_trashed", "INTEGER DEFAULT 0"),  # SQLite는 BOOLEAN 없음
    ("papers", "trashed_at", "TIMESTAMP"),
    ("papers", "trash_reason", "TEXT"),
    # folders 신규 컬럼
    ("folders", "is_system_folder", "INTEGER DEFAULT 0"),
]


# 추가할 테이블: (테이블명, CREATE SQL)
TABLES_TO_CREATE: List[Tuple[str, str]] = [
    (
        "agent_runs",
        """
        CREATE TABLE agent_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TIMESTAMP NOT NULL,
            finished_at TIMESTAMP,
            topic_snapshot TEXT,
            keywords_used TEXT,            -- JSON 배열
            candidates_fetched INTEGER DEFAULT 0,
            new_papers INTEGER DEFAULT 0,
            saved_papers INTEGER DEFAULT 0,
            trashed_papers INTEGER DEFAULT 0,
            recommended_papers INTEGER DEFAULT 0,  -- 풀분석 추천 폴더로 들어간 수
            is_dry_run INTEGER DEFAULT 0,
            error TEXT,
            duration_seconds REAL,
            decisions_json TEXT            -- 사이클이 내린 결정 상세 (디버깅/감사용)
        )
        """,
    ),
    (
        "searched_keywords",
        """
        CREATE TABLE searched_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT UNIQUE NOT NULL,
            first_searched_at TIMESTAMP NOT NULL,
            last_searched_at TIMESTAMP NOT NULL,
            hit_count INTEGER DEFAULT 1
        )
        """,
    ),
]


# 추가할 인덱스: (인덱스명, CREATE SQL)
INDEXES_TO_CREATE: List[Tuple[str, str]] = [
    (
        "idx_papers_is_trashed",
        "CREATE INDEX idx_papers_is_trashed ON papers(is_trashed)",
    ),
    (
        "idx_papers_relevance_score",
        "CREATE INDEX idx_papers_relevance_score ON papers(relevance_score)",
    ),
    (
        "idx_agent_runs_started_at",
        "CREATE INDEX idx_agent_runs_started_at ON agent_runs(started_at)",
    ),
    (
        "idx_searched_keywords_last",
        "CREATE INDEX idx_searched_keywords_last ON searched_keywords(last_searched_at)",
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


def run_migration(db_path: str) -> None:
    if not os.path.exists(db_path):
        print(f"❌ DB 파일을 찾을 수 없음: {db_path}")
        sys.exit(1)

    print(f"📂 DB: {db_path}")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    added_cols = 0
    skipped_cols = 0
    added_tables = 0
    skipped_tables = 0
    added_indexes = 0
    skipped_indexes = 0

    # 1. 컬럼 추가
    for table, column, type_def in COLUMNS_TO_ADD:
        if not table_exists(cur, table):
            print(f"⚠️  테이블 없음, 컬럼 추가 skip: {table}.{column}")
            continue
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

    # 2. 테이블 추가
    for table_name, create_sql in TABLES_TO_CREATE:
        if table_exists(cur, table_name):
            print(f"⏭  이미 존재: TABLE {table_name}")
            skipped_tables += 1
            continue
        cur.execute(create_sql)
        print(f"✅ 추가: TABLE {table_name}")
        added_tables += 1

    # 3. 인덱스 추가
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
    print(f"📊 테이블: 추가 {added_tables} / 건너뜀 {skipped_tables}")
    print(f"📊 인덱스: 추가 {added_indexes} / 건너뜀 {skipped_indexes}")
    print("✨ Migration 001 완료")


if __name__ == "__main__":
    db_arg = sys.argv[1] if len(sys.argv) > 1 else None
    if db_arg:
        run_migration(db_arg)
    else:
        # 기본: 프로젝트 루트의 data/papers.db
        here = os.path.dirname(os.path.abspath(__file__))
        default_db = os.path.normpath(os.path.join(here, "..", "..", "data", "papers.db"))
        run_migration(default_db)
