from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from collections import Counter
from typing import Optional
import asyncio
import logging
from datetime import datetime, timezone

from database import get_db
from models import (
    Paper, Collection, Tag, Folder, PaperTag,
    Alert, SearchHistory, AgentRun,
)
from services.discovery_lock import discovery_lock, LockedError, lock_path_for

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

logger = logging.getLogger(__name__)


@router.get("/stats")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """대시보드 종합 통계"""
    # 기본 카운트
    total_papers = db.query(Paper).count()
    total_collections = db.query(Collection).count()
    total_tags = db.query(Tag).count()
    total_folders = db.query(Folder).count()

    # 상태별 카운트
    unread_papers = db.query(Paper).filter(Paper.status == "unread").count()
    reading_papers = db.query(Paper).filter(Paper.status == "reading").count()
    read_papers = db.query(Paper).filter(Paper.status == "read").count()
    important_papers = db.query(Paper).filter(Paper.status == "important").count()

    # 미읽은 알림
    unread_alerts = db.query(Alert).filter(Alert.is_read == False).count()

    # 연도별 논문 수
    papers_with_year = db.query(Paper.year, func.count(Paper.id)).filter(
        Paper.year != None
    ).group_by(Paper.year).all()
    papers_by_year = {str(year): count for year, count in papers_with_year if year}

    # 학술지별 논문 수 (상위 10개)
    papers_with_venue = db.query(Paper.venue, func.count(Paper.id)).filter(
        Paper.venue != None, Paper.venue != ""
    ).group_by(Paper.venue).order_by(func.count(Paper.id).desc()).limit(10).all()
    papers_by_venue = {venue: count for venue, count in papers_with_venue}

    # 태그별 논문 수
    tag_counts = db.query(
        Tag.name, func.count(PaperTag.id)
    ).join(PaperTag, PaperTag.tag_id == Tag.id).group_by(Tag.name).all()
    papers_by_tag = {name: count for name, count in tag_counts}

    # 최근 추가 논문 5개
    recent = db.query(Paper).order_by(Paper.saved_at.desc()).limit(5).all()
    recent_papers = [
        {
            "id": p.id,
            "title": p.title,
            "year": p.year,
            "saved_at": p.saved_at.isoformat(),
        }
        for p in recent
    ]

    # 최근 검색 5개
    recent_sh = db.query(SearchHistory).order_by(SearchHistory.searched_at.desc()).limit(5).all()
    recent_searches = [
        {
            "keyword": sh.keyword,
            "result_count": sh.result_count,
            "searched_at": sh.searched_at.isoformat(),
        }
        for sh in recent_sh
    ]

    # 에이전트 사이클 정보
    last_run = db.query(AgentRun).order_by(AgentRun.id.desc()).first()
    agent_total = db.query(AgentRun).count()
    last_run_dict = None
    if last_run:
        last_run_dict = {
            "id": last_run.id,
            "started_at": last_run.started_at.isoformat() if last_run.started_at else None,
            "finished_at": last_run.finished_at.isoformat() if last_run.finished_at else None,
            "topic_snapshot": last_run.topic_snapshot,
            "candidates_fetched": last_run.candidates_fetched,
            "new_papers": last_run.new_papers,
            "saved_papers": last_run.saved_papers,
            "trashed_papers": last_run.trashed_papers,
            "recommended_papers": last_run.recommended_papers,
            "is_dry_run": bool(last_run.is_dry_run),
            "duration_seconds": last_run.duration_seconds,
            "error": last_run.error,
        }

    return {
        # Phase E: 락 파일 기반으로 판정. 외부 폴링이 잦지 않으므로 비용 OK.
        "agent_running": bool(_running_tasks),
        "agent_run_total": agent_total,
        "agent_last_run": last_run_dict,
        "total_papers": total_papers,
        "total_collections": total_collections,
        "total_tags": total_tags,
        "total_folders": total_folders,
        "unread_papers": unread_papers,
        "reading_papers": reading_papers,
        "read_papers": read_papers,
        "important_papers": important_papers,
        "unread_alerts": unread_alerts,
        "papers_by_year": papers_by_year,
        "papers_by_venue": papers_by_venue,
        "papers_by_tag": papers_by_tag,
        "recent_papers": recent_papers,
        "recent_searches": recent_searches,
    }


# ==============================================================================
# 자율 연구 에이전트: Discovery 사이클 트리거
# ==============================================================================

DEFAULT_AGENT_PROJECT = "CF4"
DEFAULT_AGENT_TOPIC = "CF4 분해 촉매와 반응 메커니즘 연구"


async def _run_discovery_with_lock(project: str, topic: str, max_candidates: int):
    """asyncio task로 1 사이클 실행. Phase E §1: 락은 task 전체 수명 동안 유지."""
    from services.research_agent import run_discovery_cycle

    try:
        with discovery_lock(project):
            try:
                report = await run_discovery_cycle(
                    project,
                    topic,
                    limit_per_query=10,
                    max_candidates=max_candidates,
                )
                logger.info(
                    f"[discovery] {project} 완료: candidates={report.candidates_fetched} "
                    f"new={report.new_papers} saved={report.auto_saved + report.recommended} "
                    f"trashed={report.trashed} duration={report.duration_seconds:.1f}s"
                )
            except Exception as e:
                logger.exception(f"[discovery] {project} 실패: {e}")
    except LockedError:
        logger.warning(f"[discovery] {project} 락 충돌, 사이클 건너뜀")


# 백그라운드 task 핸들 보관 — GC 방지 (asyncio.create_task의 weak ref 이슈)
_running_tasks: set[asyncio.Task] = set()


@router.post("/agent/run")
async def trigger_agent_run(
    background_tasks: BackgroundTasks,
    body: Optional[dict] = None,
):
    """Discovery 1 사이클을 백그라운드로 시작.

    body 옵션:
        project: 프로젝트 이름 (기본 CF4)
        topic: 주제 (기본 CF4 분해 촉매)
        max_candidates: 평가 후보 상한 (기본 60)
    """
    body = body or {}
    project = body.get("project") or DEFAULT_AGENT_PROJECT
    topic = body.get("topic") or DEFAULT_AGENT_TOPIC
    max_candidates = int(body.get("max_candidates") or 60)

    # Phase E §1: 락 파일이 이미 잡혀있으면 즉시 409.
    # 실제 락은 asyncio task 안에서 다시 잡으며, 거기서 task 전체 수명 동안 유지된다.
    # 사전 체크가 통과한 직후 다른 요청이 끼어드는 race window는 락 파일 존재 자체가
    # 아닌 fcntl flock 으로 보호되므로 두 task 중 하나만 실제 작업을 진행한다.
    if lock_path_for(project).exists():
        # 기존 메타가 남아있을 수 있으므로 실제 flock 시도로 확인
        try:
            with discovery_lock(project):
                pass
        except LockedError as e:
            raise HTTPException(
                status_code=409,
                detail=f"이미 '{project}' 사이클이 실행 중입니다 (lock={e.lock_path}).",
            )

    task = asyncio.create_task(
        _run_discovery_with_lock(project, topic, max_candidates)
    )
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)
    return {
        "ok": True,
        "project": project,
        "topic": topic,
        "max_candidates": max_candidates,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "message": "백그라운드에서 사이클을 시작했습니다. 완료까지 약 2~3분.",
    }


@router.get("/agent/status")
async def agent_status(db: Session = Depends(get_db)):
    """에이전트 실행 상태 + 최근 사이클 정보."""
    last_run = db.query(AgentRun).order_by(AgentRun.id.desc()).first()
    # Phase E §2: 락 파일 기반 running 판정 (in-process flag 제거됨)
    running: list[str] = []
    try:
        from pathlib import Path
        lock_dir = Path(__file__).resolve().parent.parent.parent / "data"
        if lock_dir.exists():
            for p in lock_dir.glob("discovery_*.lock"):
                # 락 시도 — 실패 시 누군가 잡고 있다
                try:
                    with discovery_lock(p.stem.replace("discovery_", "")):
                        pass
                except LockedError:
                    running.append(p.stem.replace("discovery_", ""))
    except Exception:
        pass

    return {
        "running_projects": running,
        "last_run": (
            {
                "id": last_run.id,
                "started_at": last_run.started_at.isoformat() if last_run.started_at else None,
                "finished_at": last_run.finished_at.isoformat() if last_run.finished_at else None,
                "topic_snapshot": last_run.topic_snapshot,
                "candidates_fetched": last_run.candidates_fetched,
                "new_papers": last_run.new_papers,
                "saved_papers": last_run.saved_papers,
                "trashed_papers": last_run.trashed_papers,
                "recommended_papers": last_run.recommended_papers,
                "is_dry_run": bool(last_run.is_dry_run),
                "duration_seconds": last_run.duration_seconds,
                "error": last_run.error,
                # Phase E §2: heartbeat 정보 (UI 연결은 Phase F)
                "heartbeat_at": last_run.heartbeat_at.isoformat() if last_run.heartbeat_at else None,
                "locked_by": last_run.locked_by,
            }
            if last_run
            else None
        ),
    }
