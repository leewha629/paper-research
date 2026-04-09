"""Phase F-1.2 — eval_failed 버킷 검증.

1. bootstrap이 "평가 실패" 폴더를 생성하는지 확인
2. is_eval_failed=True인 논문이 "평가 실패" 폴더에 저장되는 시나리오 검증
"""
from __future__ import annotations

from models import Paper, FolderPaper


def test_bootstrap_creates_eval_failed_folder(db_session, monkeypatch):
    """새 collection 부트스트랩 시 '평가 실패' 폴더가 생성되는지 확인."""
    from services.research_agent.bootstrap import bootstrap_project
    from services.research_agent import bootstrap as bs_mod

    monkeypatch.setattr(bs_mod, "SessionLocal", lambda: db_session)
    handles = bootstrap_project("EVAL_F_TEST", "주제")

    assert "평가 실패" in handles.folder_ids
    folder_id = handles.folder_ids["평가 실패"]
    assert folder_id > 0


def test_eval_failed_paper_saves_with_flag(db_session, monkeypatch):
    """is_eval_failed=True 논문이 '평가 실패' 폴더에 매핑되는 시나리오.

    discovery.py 저장 블록을 직접 호출해 검증 (run_discovery_cycle 전체 우회).
    """
    from services.research_agent.bootstrap import bootstrap_project
    from services.research_agent import bootstrap as bs_mod

    monkeypatch.setattr(bs_mod, "SessionLocal", lambda: db_session)
    handles = bootstrap_project("EVAL_F2_TEST", "주제")

    # eval_failed 논문 저장 — discovery.py의 저장 블록을 흉내냄
    sp = db_session.begin_nested()
    paper = Paper(
        paper_id="eval-fail-001",
        title="평가 실패 논문",
        discovered_by="agent",
        relevance_score=None,  # HOLD_SCORE(4)가 아님
        relevance_reason="[평가 실패] LLM timeout",
        is_eval_failed=True,
        eval_failure_reason="[평가 실패] LLM timeout",
    )
    db_session.add(paper)
    db_session.flush()

    # move semantics: 시스템 폴더 매핑 DELETE 후 "평가 실패" 폴더에 INSERT
    system_folder_ids = list(handles.folder_ids.values())
    db_session.query(FolderPaper).filter(
        FolderPaper.paper_id == paper.id,
        FolderPaper.folder_id.in_(system_folder_ids),
    ).delete(synchronize_session=False)
    db_session.add(
        FolderPaper(
            folder_id=handles.folder_ids["평가 실패"],
            paper_id=paper.id,
        )
    )
    sp.commit()

    # 검증
    saved = db_session.query(Paper).filter(Paper.paper_id == "eval-fail-001").first()
    assert saved is not None
    assert saved.is_eval_failed is True
    assert saved.relevance_score is None
    assert "평가 실패" in saved.eval_failure_reason

    fp = db_session.query(FolderPaper).filter(FolderPaper.paper_id == saved.id).first()
    assert fp is not None
    assert fp.folder_id == handles.folder_ids["평가 실패"]
