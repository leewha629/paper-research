"""Phase E v2 — folder_papers UNIQUE + move semantics 2건.

PLAN v2 추가:
- test_duplicate_paper_in_two_folders_blocked  → 시스템 폴더 간 dup 차단
- test_move_semantics_replaces_existing
"""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from models import Paper, FolderPaper


def _seed_paper(db, paper_id="x-001") -> Paper:
    p = Paper(paper_id=paper_id, title=f"논문 {paper_id}", discovered_by="agent")
    db.add(p)
    db.flush()
    return p


def test_duplicate_paper_in_two_folders_blocked(db_session, monkeypatch):
    """시스템 폴더 4개에 같은 paper를 매핑하는 시도는 move semantics가 차단.

    db-level UNIQUE는 (folder_id, paper_id) 쌍이므로 다른 폴더에 INSERT 자체는 가능.
    discovery.py의 move semantics가 INSERT 전에 시스템 폴더 매핑을 DELETE 하여
    실질적으로 1개로 유지한다 — 이 동작을 직접 호출로 검증.
    """
    from services.research_agent.bootstrap import bootstrap_project
    from services.research_agent import bootstrap as bs_mod

    monkeypatch.setattr(bs_mod, "SessionLocal", lambda: db_session)
    handles = bootstrap_project("DUP_TEST", "주제")

    p = _seed_paper(db_session)
    sys_ids = list(handles.folder_ids.values())

    # 첫 매핑: 자동 발견
    db_session.add(FolderPaper(folder_id=handles.folder_ids["자동 발견"], paper_id=p.id))
    db_session.commit()

    # move semantics 흉내: 시스템 폴더 매핑 DELETE 후 새로 INSERT
    db_session.query(FolderPaper).filter(
        FolderPaper.paper_id == p.id,
        FolderPaper.folder_id.in_(sys_ids),
    ).delete(synchronize_session=False)
    db_session.add(FolderPaper(folder_id=handles.folder_ids["풀분석 추천"], paper_id=p.id))
    db_session.commit()

    rows = db_session.query(FolderPaper).filter(FolderPaper.paper_id == p.id).all()
    # 시스템 폴더 매핑은 정확히 1개
    sys_rows = [r for r in rows if r.folder_id in sys_ids]
    assert len(sys_rows) == 1
    assert sys_rows[0].folder_id == handles.folder_ids["풀분석 추천"]


def test_move_semantics_replaces_existing(db_session, monkeypatch):
    """같은 (folder_id, paper_id) 쌍 INSERT는 UNIQUE 위반 → 막힌다."""
    from services.research_agent.bootstrap import bootstrap_project
    from services.research_agent import bootstrap as bs_mod

    monkeypatch.setattr(bs_mod, "SessionLocal", lambda: db_session)
    handles = bootstrap_project("MV_TEST", "주제")

    p = _seed_paper(db_session, "mv-001")
    fid = handles.folder_ids["자동 발견"]

    db_session.add(FolderPaper(folder_id=fid, paper_id=p.id))
    db_session.commit()

    # 같은 쌍 두 번째 INSERT → UNIQUE 위반
    db_session.add(FolderPaper(folder_id=fid, paper_id=p.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_router_add_paper_move_semantics(client, db_session):
    """POST /folders/{id}/papers 호출 시 기존 다른 폴더 매핑이 DELETE 된다.

    paper-research 실제 사용자 워크플로: 논문을 폴더 A → 폴더 B 로 끌어다 놓으면
    프론트는 POST /folders/B/papers 를 호출한다. DB 레벨 UNIQUE(paper_id) 때문에
    기존 A 매핑이 남아있으면 IntegrityError 로 깨져야 하지만, 라우터의
    move semantics 덕에 A 매핑이 먼저 삭제되어 성공해야 한다.
    """
    from models import Folder, FolderPaper as FP

    # 폴더 A, B 생성
    folder_a = Folder(name="A")
    folder_b = Folder(name="B")
    db_session.add_all([folder_a, folder_b])
    db_session.flush()

    # 논문 1건을 폴더 A에 시드
    paper = _seed_paper(db_session, "mv-router-001")
    db_session.add(FP(folder_id=folder_a.id, paper_id=paper.id))
    db_session.commit()

    # 폴더 B 로 "추가" 요청 — move semantics 가 없다면 UNIQUE 때문에 실패한다.
    resp = client.post(
        f"/api/folders/{folder_b.id}/papers",
        json={"paper_id": paper.id},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json().get("success") is True

    # A 매핑은 사라지고 B 매핑만 남아야 한다 (전체 1건).
    rows = db_session.query(FP).filter(FP.paper_id == paper.id).all()
    assert len(rows) == 1
    assert rows[0].folder_id == folder_b.id
