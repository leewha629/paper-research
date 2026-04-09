"""
Discovery 1 사이클 — legacy DB 통합판 (Option A).

주제 → 키워드 → S2 → 중복제거 → 관련도 평가 → 분류 →
legacy data/papers.db 의 papers / paper_collections / folder_papers / agent_runs / searched_keywords 에 저장.

사용자 관점:
- "내 서재 → 컬렉션 CF4" 에서 새 논문이 즉시 보임
- "폴더 → CF4 → 풀분석 추천" 으로 점수별로 좁혀보기
- 휴지통(0~3)은 is_trashed=True
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import SessionLocal
from models import (
    Paper,
    PaperCollection,
    FolderPaper,
    AgentRun,
    SearchedKeyword,
    AppSetting,
)
from s2_client import S2Client
from services.llm import (
    extract_keywords,
    score_relevance,
    StrictCallError,
)
from .bootstrap import bootstrap_project, ProjectHandles

logger = logging.getLogger(__name__)

# 분류 임계값
TRASH_MAX = 3
HOLD_SCORE = 4
AUTO_MAX = 6

# Phase E §2: heartbeat 갱신 주기 (초)
HEARTBEAT_INTERVAL_SECONDS = 30


def _classify(score: int) -> str:
    if score <= TRASH_MAX:
        return "휴지통"
    if score == HOLD_SCORE:
        return "검토 대기"
    if score <= AUTO_MAX:
        return "자동 발견"
    return "풀분석 추천"


def _load_s2_api_key(db: Session) -> Optional[str]:
    row = (
        db.query(AppSetting)
        .filter(AppSetting.key == "semantic_scholar_api_key")
        .first()
    )
    return row.value if row and row.value else None


@dataclass
class DiscoveryReport:
    project: str
    topic: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    keywords_used: List[str] = field(default_factory=list)
    candidates_fetched: int = 0
    new_papers: int = 0
    trashed: int = 0
    holding: int = 0
    auto_saved: int = 0
    recommended: int = 0
    score_distribution: Dict[int, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    is_dry_run: bool = False
    decisions: List[dict] = field(default_factory=list)


def _normalize_paper_record(p: dict) -> Optional[dict]:
    pid = p.get("paperId")
    title = p.get("title")
    if not pid or not title:
        return None
    return {
        "paper_id": pid,
        "title": title,
        "authors_json": json.dumps(p.get("authors") or [], ensure_ascii=False),
        "year": p.get("year"),
        "venue": p.get("venue"),
        "abstract": p.get("abstract"),
        "doi": (p.get("externalIds") or {}).get("DOI"),
        "citation_count": p.get("citationCount") or 0,
        "reference_count": p.get("referenceCount") or 0,
        "is_open_access": bool(p.get("isOpenAccess")),
        "pdf_url": (p.get("openAccessPdf") or {}).get("url"),
        "external_ids_json": json.dumps(p.get("externalIds") or {}, ensure_ascii=False),
        "fields_of_study_json": json.dumps(p.get("fieldsOfStudy") or [], ensure_ascii=False),
    }


def _existing_paper_ids(db: Session) -> set[str]:
    rows = db.query(Paper.paper_id).all()
    return {r[0] for r in rows if r[0]}


def _load_recent_keywords(db: Session, limit: int = 30) -> List[str]:
    rows = (
        db.query(SearchedKeyword.keyword)
        .order_by(SearchedKeyword.last_searched_at.desc())
        .limit(limit)
        .all()
    )
    return [r[0] for r in rows if r[0]]


def _record_keywords(db: Session, keywords: List[str]) -> None:
    now = datetime.utcnow()
    for kw in keywords:
        existing = (
            db.query(SearchedKeyword).filter(SearchedKeyword.keyword == kw).first()
        )
        if existing:
            existing.last_searched_at = now
            existing.hit_count = (existing.hit_count or 0) + 1
        else:
            db.add(
                SearchedKeyword(
                    keyword=kw,
                    first_searched_at=now,
                    last_searched_at=now,
                    hit_count=1,
                )
            )


def _locked_by_label() -> str:
    """heartbeat 메타: hostname:pid."""
    try:
        host = socket.gethostname()
    except Exception:
        host = "unknown"
    return f"{host}:{os.getpid()}"


async def _heartbeat_loop(db_factory, run_id: int) -> None:
    """30s마다 AgentRun.heartbeat_at 갱신. 사이클 종료 시 cancel."""
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            try:
                hb_db = db_factory()
                try:
                    row = hb_db.query(AgentRun).filter(AgentRun.id == run_id).first()
                    if row is not None:
                        row.heartbeat_at = datetime.utcnow()
                        hb_db.commit()
                finally:
                    hb_db.close()
            except Exception as e:  # heartbeat 실패는 사이클을 죽이지 않는다
                logger.warning(f"heartbeat 갱신 실패 (run_id={run_id}): {e}")
    except asyncio.CancelledError:
        return


async def run_discovery_cycle(
    project_name: str,
    topic: str,
    *,
    limit_per_query: int = 10,
    max_candidates: int = 60,
    dry_run: bool = False,
) -> DiscoveryReport:
    """1 사이클 실행. 부트스트랩 + 검색 + 평가 + 저장 + 로그.

    Phase E §2: 사이클 시작 시 AgentRun INSERT, 30s마다 heartbeat 갱신,
    종료 시 task cancel + 마지막 heartbeat 기록.
    """
    handles: ProjectHandles = bootstrap_project(project_name, topic)

    report = DiscoveryReport(
        project=project_name,
        topic=topic,
        started_at=datetime.utcnow(),
        is_dry_run=dry_run,
    )
    t0 = time.time()

    # ─── heartbeat: 사이클 시작 시 INSERT ──────────────────────────────
    locked_by = _locked_by_label()
    init_db = SessionLocal()
    try:
        initial_run = AgentRun(
            started_at=report.started_at,
            topic_snapshot=topic,
            is_dry_run=bool(dry_run),
            heartbeat_at=report.started_at,
            locked_by=locked_by,
        )
        init_db.add(initial_run)
        init_db.commit()
        run_id = initial_run.id
    finally:
        init_db.close()

    heartbeat_task = asyncio.create_task(_heartbeat_loop(SessionLocal, run_id))

    db = SessionLocal()
    try:
        # 1) 키워드
        recent = _load_recent_keywords(db)
        try:
            kw_obj = await extract_keywords(topic, exclude=recent)
            keywords = kw_obj.keywords
        except StrictCallError as e:
            report.errors.append(f"extract_keywords 실패: {e}")
            keywords = []
        report.keywords_used = keywords
        logger.info(f"[discovery:{project_name}] 키워드 {len(keywords)}: {keywords}")

        if not keywords:
            report.finished_at = datetime.utcnow()
            report.duration_seconds = time.time() - t0
            _persist_run(db, report, run_id=run_id)
            return report

        # 2) S2 검색
        s2 = S2Client(api_key=_load_s2_api_key(db))
        try:
            raw = await s2.bulk_search(keywords, limit_per_query=limit_per_query)
        except Exception as e:
            report.errors.append(f"S2 bulk_search 실패: {e}")
            raw = []
        report.candidates_fetched = len(raw)

        # 3) 중복 제거
        seen = _existing_paper_ids(db)
        in_batch: set[str] = set()
        candidates: List[dict] = []
        for r in raw:
            n = _normalize_paper_record(r)
            if not n:
                continue
            if n["paper_id"] in seen or n["paper_id"] in in_batch:
                continue
            in_batch.add(n["paper_id"])
            candidates.append(n)
            if len(candidates) >= max_candidates:
                break
        report.new_papers = len(candidates)
        logger.info(f"[discovery:{project_name}] 신규 후보 {len(candidates)}")

        # 4) 평가 + 분류 + 저장
        for cand in candidates:
            eval_failed_flag = False
            try:
                judgment = await score_relevance(
                    topic, cand["title"], cand["abstract"] or ""
                )
                score = judgment.score
                reason = judgment.reason
            except StrictCallError as e:
                # Phase F-1.2: HOLD_SCORE 폴백 제거 (Phase C fail-loud 원칙 위반).
                # 논문은 저장하되 "평가 실패" 폴더로 명시 라우팅.
                report.errors.append(f"score_relevance 실패 ({cand['paper_id']}): {e}")
                score = None
                reason = f"[평가 실패] {str(e)[:200]}"
                eval_failed_flag = True

            if eval_failed_flag:
                bucket = "평가 실패"
            else:
                bucket = _classify(score)

            report.score_distribution[score] = report.score_distribution.get(score, 0) + 1
            report.decisions.append(
                {
                    "paper_id": cand["paper_id"],
                    "title": cand["title"][:100],
                    "score": score,
                    "bucket": bucket,
                    "reason": reason,
                }
            )

            if bucket == "휴지통":
                report.trashed += 1
            elif bucket == "검토 대기":
                report.holding += 1
            elif bucket == "자동 발견":
                report.auto_saved += 1
            elif bucket == "평가 실패":
                report.eval_failed = getattr(report, "eval_failed", 0) + 1
            else:
                report.recommended += 1

            if dry_run:
                continue

            # Phase E §5: paper / paper_collections / folder_papers 저장을
            # 단일 savepoint로 묶어 부분 실패 시 원자적 롤백.
            sp = db.begin_nested()
            try:
                paper = Paper(
                    paper_id=cand["paper_id"],
                    title=cand["title"],
                    authors_json=cand["authors_json"],
                    year=cand["year"],
                    venue=cand["venue"],
                    abstract=cand["abstract"],
                    doi=cand["doi"],
                    citation_count=cand["citation_count"],
                    reference_count=cand["reference_count"],
                    is_open_access=cand["is_open_access"],
                    pdf_url=cand["pdf_url"],
                    external_ids_json=cand["external_ids_json"],
                    fields_of_study_json=cand["fields_of_study_json"],
                    discovered_by="agent",
                    relevance_score=score,
                    relevance_reason=reason,
                    relevance_checked_at=datetime.utcnow(),
                    is_trashed=(bucket == "휴지통"),
                    trashed_at=(datetime.utcnow() if bucket == "휴지통" else None),
                    trash_reason=("low_relevance" if bucket == "휴지통" else None),
                    is_eval_failed=eval_failed_flag,
                    eval_failure_reason=(reason if eval_failed_flag else None),
                )
                db.add(paper)
                db.flush()  # paper.id 확보

                # 컬렉션 (CF4) 매핑
                db.add(
                    PaperCollection(
                        paper_id=paper.id,
                        collection_id=handles.collection_id,
                    )
                )

                # Phase E §4: 분류 폴더 매핑 — move semantics.
                # 시스템 폴더 5종 중 기존 매핑이 있으면 DELETE 후 새로 INSERT.
                # 사용자 폴더는 건드리지 않는다.
                system_folder_ids = list(handles.folder_ids.values())
                db.query(FolderPaper).filter(
                    FolderPaper.paper_id == paper.id,
                    FolderPaper.folder_id.in_(system_folder_ids),
                ).delete(synchronize_session=False)
                db.add(
                    FolderPaper(
                        folder_id=handles.folder_ids[bucket],
                        paper_id=paper.id,
                    )
                )
                sp.commit()
            except (IntegrityError, Exception) as e:
                sp.rollback()
                logger.error(
                    f"[discovery:{project_name}] 저장 실패 paper_id={cand['paper_id']}: {e}"
                )
                report.errors.append(
                    f"save 실패 ({cand['paper_id']}): {str(e)[:120]}"
                )

        # 5) 키워드 기록 + 커밋
        if not dry_run:
            _record_keywords(db, keywords)
            db.commit()

        report.finished_at = datetime.utcnow()
        report.duration_seconds = time.time() - t0

        _persist_run(db, report, run_id=run_id)
        return report
    finally:
        db.close()
        # heartbeat task 정리 (예외/정상 종료 어느 경우든)
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except (asyncio.CancelledError, Exception):
            pass
        # 마지막 heartbeat 기록
        try:
            final_db = SessionLocal()
            try:
                row = final_db.query(AgentRun).filter(AgentRun.id == run_id).first()
                if row is not None:
                    row.heartbeat_at = datetime.utcnow()
                    final_db.commit()
            finally:
                final_db.close()
        except Exception as e:
            logger.warning(f"마지막 heartbeat 기록 실패: {e}")


def _persist_run(db: Session, report: DiscoveryReport, *, run_id: int) -> None:
    """사이클 시작 시 INSERT한 AgentRun을 종료 메타로 UPDATE."""
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if run is None:
        # 비정상 — 시작 row가 사라졌다. 새로 INSERT 폴백.
        run = AgentRun(started_at=report.started_at)
        db.add(run)
    run.finished_at = report.finished_at or datetime.utcnow()
    run.topic_snapshot = report.topic
    run.keywords_used = json.dumps(report.keywords_used, ensure_ascii=False)
    run.candidates_fetched = report.candidates_fetched
    run.new_papers = report.new_papers
    run.saved_papers = report.auto_saved + report.recommended + report.holding
    run.trashed_papers = report.trashed
    run.recommended_papers = report.recommended
    run.is_dry_run = bool(report.is_dry_run)
    run.error = "\n".join(report.errors) if report.errors else None
    run.duration_seconds = report.duration_seconds
    run.decisions_json = json.dumps(report.decisions, ensure_ascii=False)
    run.heartbeat_at = datetime.utcnow()
    try:
        db.commit()
    except Exception as e:
        logger.warning(f"AgentRun 기록 실패: {e}")
        db.rollback()
