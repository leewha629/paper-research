"""
Migration 003: Phase E — heartbeat 컬럼 + folder_papers UNIQUE + Folder UNIQUE + paper 99 cleanup

추가/변경되는 것:
- agent_runs 컬럼:
    heartbeat_at TIMESTAMP
    locked_by    TEXT
- folder_papers:
    (a) 중복 row 정리 — 각 paper_id마다 가장 최근(folder_papers.id 최대) 매핑만 유지
        → paper 99 사고 자동 처리됨
    (b) UNIQUE INDEX (folder_id, paper_id)
- folders:
    UNIQUE INDEX (parent_id, name) — bootstrap 멱등 보장

특징:
- 멱등 (이미 적용된 컬럼/인덱스는 skip)
- DB 적용 전 자동 백업 → data/backups/papers_pre_003_<ts>.db
- 직접 실행 가능: `python backend/migrations/003_phase_e_lock_heartbeat_unique.py [db_path]`

⚠️  사용자 승인 필수:
    이 마이그레이션은 folder_papers 중복 row를 삭제한다 (paper 99 등 알려진 사고 정리).
    실행 전 ~/.claude의 호출 흐름은 사용자에게 명시 알림 + 응답 대기를 보장한다.

배경:
- Phase E §4 — paper 99: 같은 paper_id가 두 system folder에 동시 존재하던 사고.
- (folder_id, paper_id) UNIQUE 만으로는 한 paper를 두 다른 폴더에 둘 수 있으므로,
  cleanup 단계에서 paper_id 당 1개로 강제 후 UNIQUE로 dup row 자체를 막는다.
- 사용자 폴더(시스템 폴더 외)는 보존되지 않을 수 있으나, 본 cleanup은 "각 paper_id 1개"
  정책을 따르며, recalibrate.py는 시스템 폴더만 건드리는 가정을 유지한다.
"""
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from typing import List, Tuple


COLUMNS_TO_ADD: List[Tuple[str, str, str]] = [
    ("agent_runs", "heartbeat_at", "TIMESTAMP"),
    ("agent_runs", "locked_by", "TEXT"),
]

INDEXES_TO_CREATE: List[Tuple[str, str]] = [
    (
        "uq_folder_papers_folder_paper",
        "CREATE UNIQUE INDEX uq_folder_papers_folder_paper ON folder_papers(folder_id, paper_id)",
    ),
    (
        "uq_folders_parent_name",
        # SQLite는 NULL이 unique 비교에서 distinct로 간주되므로 parent_id IS NULL 케이스는
        # 아래 partial index 또는 별도 처리 필요. 여기선 두 인덱스를 만든다.
        "CREATE UNIQUE INDEX uq_folders_parent_name ON folders(parent_id, name) WHERE parent_id IS NOT NULL",
    ),
    (
        "uq_folders_root_name",
        "CREATE UNIQUE INDEX uq_folders_root_name ON folders(name) WHERE parent_id IS NULL",
    ),
    (
        "idx_agent_runs_heartbeat",
        "CREATE INDEX idx_agent_runs_heartbeat ON agent_runs(heartbeat_at)",
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
    backup_path = os.path.join(backups_dir, f"papers_pre_003_{ts}.db")
    shutil.copy2(db_path, backup_path)
    print(f"💾 백업 생성: {backup_path}")
    return backup_path


def cleanup_folder_papers_duplicates(cur: sqlite3.Cursor) -> Tuple[int, List[Tuple[int, int]]]:
    """각 paper_id당 가장 큰 folder_papers.id (가장 최근) 만 남기고 나머지 DELETE.

    반환: (삭제된 행 수, 삭제된 (paper_id, folder_id) 목록)
    """
    cur.execute(
        """
        SELECT paper_id, COUNT(*) AS c
        FROM folder_papers
        GROUP BY paper_id
        HAVING c > 1
        """
    )
    dup_paper_ids = [row[0] for row in cur.fetchall()]
    if not dup_paper_ids:
        print("✅ folder_papers 중복 0건 — cleanup 건너뜀")
        return 0, []

    print(f"🧹 folder_papers 중복 paper_id {len(dup_paper_ids)}건 발견")
    deleted_pairs: List[Tuple[int, int]] = []
    deleted_count = 0
    for pid in dup_paper_ids:
        cur.execute(
            "SELECT id, folder_id FROM folder_papers WHERE paper_id=? ORDER BY id DESC",
            (pid,),
        )
        rows = cur.fetchall()
        # 첫 번째(가장 큰 id)만 유지
        keep = rows[0]
        for fp_id, folder_id in rows[1:]:
            cur.execute("DELETE FROM folder_papers WHERE id=?", (fp_id,))
            deleted_pairs.append((pid, folder_id))
            deleted_count += 1
        print(f"   paper_id={pid}: 유지 fp_id={keep[0]}(folder={keep[1]}), 삭제 {len(rows)-1}건")

    return deleted_count, deleted_pairs


def cleanup_pair_duplicates(cur: sqlite3.Cursor) -> int:
    """(folder_id, paper_id) 동일 쌍 중복도 정리 — UNIQUE INDEX 적용 전 필수."""
    cur.execute(
        """
        SELECT folder_id, paper_id, COUNT(*) AS c
        FROM folder_papers
        GROUP BY folder_id, paper_id
        HAVING c > 1
        """
    )
    rows = cur.fetchall()
    if not rows:
        return 0
    deleted = 0
    for folder_id, paper_id, _ in rows:
        cur.execute(
            "SELECT id FROM folder_papers WHERE folder_id=? AND paper_id=? ORDER BY id DESC",
            (folder_id, paper_id),
        )
        ids = [r[0] for r in cur.fetchall()]
        for fp_id in ids[1:]:
            cur.execute("DELETE FROM folder_papers WHERE id=?", (fp_id,))
            deleted += 1
    print(f"🧹 (folder_id, paper_id) 쌍 중복 {deleted}건 삭제")
    return deleted


def cleanup_folders_parent_name_duplicates(cur: sqlite3.Cursor) -> int:
    """folders 동일 (parent_id, name) 중복 — bootstrap 시 누적된 잔재 정리."""
    cur.execute(
        """
        SELECT parent_id, name, COUNT(*) AS c
        FROM folders
        GROUP BY parent_id, name
        HAVING c > 1
        """
    )
    rows = cur.fetchall()
    if not rows:
        return 0
    deleted = 0
    for parent_id, name, _ in rows:
        if parent_id is None:
            cur.execute(
                "SELECT id FROM folders WHERE parent_id IS NULL AND name=? ORDER BY id ASC",
                (name,),
            )
        else:
            cur.execute(
                "SELECT id FROM folders WHERE parent_id=? AND name=? ORDER BY id ASC",
                (parent_id, name),
            )
        ids = [r[0] for r in cur.fetchall()]
        # 가장 오래된(가장 작은 id) 폴더를 유지 — 하위 매핑 보존 가능성 더 높음
        keep = ids[0]
        for dup_id in ids[1:]:
            # 자식 폴더의 parent_id 재배치 + folder_papers 재배치
            cur.execute("UPDATE folders SET parent_id=? WHERE parent_id=?", (keep, dup_id))
            cur.execute("UPDATE folder_papers SET folder_id=? WHERE folder_id=?", (keep, dup_id))
            cur.execute("DELETE FROM folders WHERE id=?", (dup_id,))
            deleted += 1
            print(f"   folders 중복 정리: dup_id={dup_id} → keep={keep} (parent={parent_id}, name={name!r})")
    return deleted


def run_migration(db_path: str) -> None:
    if not os.path.exists(db_path):
        print(f"❌ DB 파일을 찾을 수 없음: {db_path}")
        sys.exit(1)

    print(f"📂 DB: {db_path}")
    backup_db(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    if not table_exists(cur, "agent_runs"):
        print("⚠️  agent_runs 테이블이 없음. Migration 001을 먼저 실행하세요.")
        conn.close()
        sys.exit(2)
    if not table_exists(cur, "folder_papers"):
        print("⚠️  folder_papers 테이블이 없음.")
        conn.close()
        sys.exit(2)

    added_cols = 0
    skipped_cols = 0
    added_indexes = 0
    skipped_indexes = 0

    # 1. 컬럼 추가
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

    # 2. 중복 정리 (인덱스 적용 전 필수)
    print()
    print("─── folder_papers 중복 정리 ───")
    paper_dup_deleted, _ = cleanup_folder_papers_duplicates(cur)
    pair_dup_deleted = cleanup_pair_duplicates(cur)

    print()
    print("─── folders 중복 정리 ───")
    folder_dup_deleted = cleanup_folders_parent_name_duplicates(cur)

    # 3. 인덱스 추가
    print()
    print("─── 인덱스 ───")
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
            print("   ↳ 중복 row가 남아있을 수 있습니다. 위 cleanup 로그를 확인하세요.")

    conn.commit()
    conn.close()

    print()
    print(f"📊 컬럼: 추가 {added_cols} / 건너뜀 {skipped_cols}")
    print(f"📊 folder_papers 중복 삭제: paper_id 기준 {paper_dup_deleted}, pair 기준 {pair_dup_deleted}")
    print(f"📊 folders 중복 삭제: {folder_dup_deleted}")
    print(f"📊 인덱스: 추가 {added_indexes} / 건너뜀 {skipped_indexes}")
    print("✨ Migration 003 완료")


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
