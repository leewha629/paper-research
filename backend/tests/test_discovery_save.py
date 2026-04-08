"""Phase E §A.2 — Discovery 저장 트랜잭션 1건.

PLAN §A.2 Phase E:
- test_partial_failure_rolls_back_paper_collection_folder
"""
from __future__ import annotations

import pytest

from models import Paper, PaperCollection, FolderPaper


def test_partial_failure_rolls_back_paper_collection_folder(db_session, monkeypatch):
    """폴더 매핑이 IntegrityError로 실패하면 같은 사이클의 paper/paper_collection도 롤백.

    검증 방법: discovery 저장 블록을 직접 호출 (run_discovery_cycle 전체 대신).
    같은 paper_id로 두 번째 저장을 시도 → unique 위반 → savepoint 롤백 → DB 무변경.
    """
    from services.research_agent.bootstrap import bootstrap_project
    from services.research_agent import bootstrap as bs_mod

    monkeypatch.setattr(bs_mod, "SessionLocal", lambda: db_session)
    handles = bootstrap_project("SAVE_TEST", "주제")

    # 첫 번째 paper 저장 — 직접 INSERT
    p1 = Paper(
        paper_id="dup-001",
        title="첫 논문",
        discovered_by="agent",
    )
    db_session.add(p1)
    db_session.flush()
    db_session.add(PaperCollection(paper_id=p1.id, collection_id=handles.collection_id))
    db_session.add(FolderPaper(folder_id=handles.folder_ids["자동 발견"], paper_id=p1.id))
    db_session.commit()

    # 같은 paper_id로 다시 시도 — savepoint 안에서 unique 위반
    sp = db_session.begin_nested()
    rolled_back = False
    try:
        p2 = Paper(paper_id="dup-001", title="중복 논문", discovered_by="agent")
        db_session.add(p2)
        db_session.flush()  # ← UNIQUE 위반
        db_session.add(PaperCollection(paper_id=p2.id, collection_id=handles.collection_id))
        sp.commit()
    except Exception:
        sp.rollback()
        rolled_back = True

    assert rolled_back, "savepoint가 롤백되어야 한다"

    # paper_collections / folder_papers 모두 1건씩만 (롤백된 두 번째 시도가 남아있지 않아야)
    assert db_session.query(Paper).filter(Paper.paper_id == "dup-001").count() == 1
    assert db_session.query(PaperCollection).count() == 1
    assert db_session.query(FolderPaper).count() == 1
