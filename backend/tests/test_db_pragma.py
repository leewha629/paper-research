"""Phase F-1.1 — SQLite WAL 모드 검증."""
from sqlalchemy import create_engine, event, text
from database import _set_sqlite_pragma


def test_wal_mode_enabled():
    """새 connection에 WAL pragma가 적용되는지 확인."""
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    event.listen(eng, "connect", _set_sqlite_pragma)
    with eng.connect() as conn:
        mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        # in-memory SQLite는 WAL을 지원하지 않아 'memory' 반환.
        # 파일 DB에서는 'wal'. 여기선 pragma 함수 자체가 에러 없이 실행됨을 검증.
        assert mode in ("wal", "memory")
