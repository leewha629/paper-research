"""Phase E §A.2 — bootstrap ACID 1건.

PLAN §A.2 Phase E:
- test_concurrent_collection_creation_idempotent
"""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from models import Collection, Folder
from services.research_agent.bootstrap import bootstrap_project
from services.research_agent import bootstrap as bs_mod


def test_concurrent_collection_creation_idempotent(db_session, monkeypatch):
    """같은 collection을 두 번 bootstrap 해도 row는 1개, IntegrityError 폴백 동작."""
    monkeypatch.setattr(bs_mod, "SessionLocal", lambda: db_session)

    h1 = bootstrap_project("ACID_TEST", "주제 1")
    h2 = bootstrap_project("ACID_TEST", "주제 2")

    assert h1.collection_id == h2.collection_id
    cols = db_session.query(Collection).filter(Collection.name == "ACID_TEST").all()
    assert len(cols) == 1

    # 시스템 폴더 4종 + parent 1 = 5개만 (parent_id 같은 부모 아래)
    parents = db_session.query(Folder).filter(
        Folder.name == "ACID_TEST", Folder.parent_id.is_(None)
    ).all()
    assert len(parents) == 1
    children = db_session.query(Folder).filter(Folder.parent_id == parents[0].id).all()
    assert len(children) == 4
