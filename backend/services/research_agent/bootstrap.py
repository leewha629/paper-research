"""
프로젝트 부트스트랩 — legacy DB 통합판 (Option A).

격리 DB 대신 기존 data/papers.db 안에서:
- Collection (예: "CF4") 보장 — 웹앱 사이드바에 노출
- parent Folder (예: "CF4") + 4개 sub-folder 시드:
    · 자동 발견   (5~6)
    · 풀분석 추천 (7~9)
    · 검토 대기   (4)
    · 휴지통      (0~3)

→ "내 서재 → 컬렉션 CF4"에서 39건 전체가 보이고,
   "폴더 → CF4 → 풀분석 추천"에서 27건만 좁혀 볼 수 있음.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Collection, Folder

# (이름, 표시순서) — Discovery가 score를 이 4개 중 하나로 매핑
SYSTEM_FOLDER_NAMES: List[str] = [
    "풀분석 추천",   # 7~10
    "자동 발견",     # 5~6
    "검토 대기",     # 4
    "평가 실패",     # LLM 평가 실패 (Phase F-1.2)
    "휴지통",        # 0~3
]


@dataclass
class ProjectHandles:
    name: str
    topic: str
    collection_id: int
    parent_folder_id: int
    folder_ids: Dict[str, int]  # 시스템 폴더 이름 → folder.id


def _ensure_collection(db: Session, name: str) -> Collection:
    """ACID-safe upsert: SELECT → INSERT → IntegrityError 폴백 SELECT.

    동시에 두 워커가 같은 collection을 만들려 할 때 한 쪽이 IntegrityError를 받고
    다른 쪽이 만든 row를 SELECT로 복구한다 (Phase E §3).
    """
    col = db.query(Collection).filter(Collection.name == name).first()
    if col is not None:
        return col

    sp = db.begin_nested()  # savepoint
    try:
        col = Collection(name=name, description=f"자율 연구 에이전트 프로젝트 ({name})")
        db.add(col)
        sp.commit()
        return col
    except IntegrityError:
        sp.rollback()
        col = db.query(Collection).filter(Collection.name == name).first()
        if col is None:
            raise
        return col


def _ensure_folder(
    db: Session,
    name: str,
    *,
    parent_id: int | None,
    is_system: bool,
) -> Folder:
    """ACID-safe upsert (Phase E §3). UNIQUE(parent_id, name) 의존."""
    q = db.query(Folder).filter(Folder.name == name)
    if parent_id is None:
        q = q.filter(Folder.parent_id.is_(None))
    else:
        q = q.filter(Folder.parent_id == parent_id)
    f = q.first()
    if f is not None:
        return f

    sp = db.begin_nested()
    try:
        f = Folder(name=name, parent_id=parent_id, is_system_folder=is_system)
        db.add(f)
        sp.commit()
        return f
    except IntegrityError:
        sp.rollback()
        q = db.query(Folder).filter(Folder.name == name)
        if parent_id is None:
            q = q.filter(Folder.parent_id.is_(None))
        else:
            q = q.filter(Folder.parent_id == parent_id)
        f = q.first()
        if f is None:
            raise
        return f


def bootstrap_project(name: str, topic: str) -> ProjectHandles:
    """legacy DB에 컬렉션/폴더 트리를 멱등하게 시드하고 핸들 반환.

    Phase E §3: ACID 보강 — IntegrityError 폴백 패턴으로 동시 호출 안전.
    """
    db = SessionLocal()
    try:
        col = _ensure_collection(db, name)
        parent = _ensure_folder(db, name, parent_id=None, is_system=True)

        folder_ids: Dict[str, int] = {}
        for fname in SYSTEM_FOLDER_NAMES:
            sub = _ensure_folder(db, fname, parent_id=parent.id, is_system=True)
            folder_ids[fname] = sub.id

        db.commit()
        return ProjectHandles(
            name=name,
            topic=topic,
            collection_id=col.id,
            parent_folder_id=parent.id,
            folder_ids=folder_ids,
        )
    finally:
        db.close()
