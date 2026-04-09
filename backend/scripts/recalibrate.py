"""Phase D v2 — Collection-격리 재캘리브레이션 스크립트.

사양: .claude/prompts/refactor_score_calibration_v2.md

핵심 차이 (vs recalibrate_50.py):
1. **--collection 필수**: 컬렉션 격리 안 하면 다른 도메인 (CPN/CPL, AI/3D) 자료가
   CF4 RELEVANCE_SYSTEM으로 평가받아 휴지통 행이 되는 사고를 방지.
2. **--dry-run 진짜 동작**: folder_papers 변경 없음, agent_runs row 없음,
   paper.relevance_score 갱신 없음. 오직 docs/CALIBRATION_DIFF_<collection>_<ts>.md 만 작성.
3. **자동 백업**: 비-dry-run 시 data/backups/papers_pre_recalibrate_<ts>.db 로 SQLite 파일 복사.
4. **산출물 분리**: docs/CALIBRATION_DIFF_<collection>_<ts>.md (collection 별).

사용:
    cd backend
    ../venv/bin/python -m scripts.recalibrate --collection CF4 --dry-run
    ../venv/bin/python -m scripts.recalibrate --collection CF4
    ../venv/bin/python -m scripts.recalibrate --collection CF4 --limit 10 --dry-run

전제:
- ollama가 실행 중이고 gemma4:e4b 모델이 로드 가능
- Collection 테이블에 인자로 받은 이름의 row가 존재
- folders 테이블에 4개 시스템 폴더가 시드되어 있음

금지 (spec):
- collection 미지정 호출 (실행 거부 — exit 1)
- 기존 agent_runs row 덮어쓰기 → 항상 새 row insert
- 기존 backup 파일 삭제
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# backend/를 sys.path에 추가
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy.orm import Session

from database import SessionLocal, DB_PATH
from models import AgentRun, Collection, Folder, FolderPaper, Paper, PaperCollection
from services.llm import RelevanceJudgment, StrictCallError
from services.llm.tasks import score_relevance

logger = logging.getLogger("recalibrate")
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")

# Phase D 임계값 — 기존 recalibrate_50.py와 동일
THRESHOLD_FULL = 7
THRESHOLD_AUTO = 5
THRESHOLD_HOLD = 4

DEFAULT_TOPIC = "CF₄ catalytic decomposition / hydrolysis (Lewis acid Al/Zr/Ga/W/Ce 산화물)"

FOLDER_NAMES = {
    "full": "풀분석 추천",
    "auto": "자동 발견",
    "hold": "검토 대기",
    "trash": "휴지통",
}


def classify(score: int) -> str:
    if score >= THRESHOLD_FULL:
        return "full"
    if score >= THRESHOLD_AUTO:
        return "auto"
    if score == THRESHOLD_HOLD:
        return "hold"
    return "trash"


def load_collection(db: Session, name: str) -> Collection:
    col = db.query(Collection).filter(Collection.name == name).one_or_none()
    if col is None:
        existing = [r.name for r in db.query(Collection).order_by(Collection.name).all()]
        raise SystemExit(
            f"ERROR: collection '{name}' not found. "
            f"existing: {existing}"
        )
    return col


def load_target_papers(
    db: Session, collection: Collection, limit: Optional[int]
) -> List[Paper]:
    """주어진 collection에 속한 paper만 조회. paper.id 오름차순."""
    q = (
        db.query(Paper)
        .join(PaperCollection, PaperCollection.paper_id == Paper.id)
        .filter(PaperCollection.collection_id == collection.id)
        .order_by(Paper.id.asc())
    )
    if limit:
        q = q.limit(limit)
    return q.all()


def load_folder_ids(db: Session) -> dict[str, int]:
    rows = db.query(Folder).filter(Folder.name.in_(FOLDER_NAMES.values())).all()
    name_to_id = {r.name: r.id for r in rows}
    out: dict[str, int] = {}
    for k, v in FOLDER_NAMES.items():
        if v in name_to_id:
            out[k] = name_to_id[v]
        else:
            raise RuntimeError(f"folders 테이블에 '{v}' 폴더가 없습니다.")
    return out


def reassign_folder(
    db: Session,
    paper: Paper,
    target_folder_id: int,
    system_folder_ids: set[int],
) -> None:
    """시스템 폴더 매핑만 갱신. 사용자 컬렉션 폴더는 건드리지 않음."""
    db.query(FolderPaper).filter(
        FolderPaper.paper_id == paper.id,
        FolderPaper.folder_id.in_(system_folder_ids),
    ).delete(synchronize_session=False)
    db.add(FolderPaper(folder_id=target_folder_id, paper_id=paper.id))


def current_system_folder_name(
    db: Session, internal_paper_id: int, folder_ids: dict[str, int]
) -> Optional[str]:
    id_to_key = {v: k for k, v in folder_ids.items()}
    rows = (
        db.query(FolderPaper)
        .filter(FolderPaper.paper_id == internal_paper_id)
        .all()
    )
    for fp in rows:
        if fp.folder_id in id_to_key:
            return FOLDER_NAMES[id_to_key[fp.folder_id]]
    return None


def make_backup(ts: str) -> Path:
    """SQLite 파일을 data/backups/papers_pre_recalibrate_<ts>.db 로 복사."""
    src = Path(DB_PATH)
    if not src.exists():
        raise RuntimeError(f"DB 파일을 찾을 수 없습니다: {src}")
    backup_dir = src.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    dst = backup_dir / f"papers_pre_recalibrate_{ts}.db"
    shutil.copy2(src, dst)
    logger.info(f"백업 생성: {dst}")
    return dst


async def recalibrate_one(
    paper: Paper,
    topic: str,
) -> tuple[Optional[RelevanceJudgment], Optional[str]]:
    try:
        judgment = await score_relevance(
            topic, paper.title or "", paper.abstract or ""
        )
        return judgment, None
    except StrictCallError as e:
        return None, f"StrictCallError: {str(e)[:200]}"
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:200]}"


async def main_async(args: argparse.Namespace) -> int:
    db: Session = SessionLocal()
    started_at = datetime.now(timezone.utc)
    ts = started_at.strftime("%Y%m%d_%H%M%S")
    t0 = time.time()
    decisions: List[dict] = []
    errors: List[str] = []
    backup_path: Optional[Path] = None

    try:
        collection = load_collection(db, args.collection)
        papers = load_target_papers(db, collection, limit=args.limit)
        logger.info(
            f"collection='{collection.name}' (id={collection.id}) "
            f"대상 논문 {len(papers)}건 로드"
        )
        if not papers:
            logger.warning("대상 논문 0건. 종료.")
            return 0

        folder_ids = load_folder_ids(db)
        system_folder_ids = set(folder_ids.values())
        topic = args.topic or DEFAULT_TOPIC

        # 비-dry-run 시 사전 백업
        if not args.dry_run:
            backup_path = make_backup(ts)

        for i, paper in enumerate(papers, 1):
            before_score = paper.relevance_score
            before_folder = current_system_folder_name(db, paper.id, folder_ids)

            judgment, err = await recalibrate_one(paper, topic)
            if judgment is None:
                errors.append(f"[{paper.id}] {err}")
                logger.warning(
                    f"({i}/{len(papers)}) {(paper.title or '')[:60]}: 실패 — {err}"
                )
                decisions.append(
                    {
                        "paper_id": paper.paper_id,
                        "internal_id": paper.id,
                        "title": (paper.title or "")[:140],
                        "before_score": before_score,
                        "before_folder": before_folder,
                        "after_score": None,
                        "after_folder": None,
                        "matched_tokens": [],
                        "reason": f"FAILED: {err}",
                    }
                )
                continue

            after_bucket = classify(judgment.score)
            after_folder = FOLDER_NAMES[after_bucket]

            decisions.append(
                {
                    "paper_id": paper.paper_id,
                    "internal_id": paper.id,
                    "title": (paper.title or "")[:140],
                    "before_score": before_score,
                    "before_folder": before_folder,
                    "after_score": judgment.score,
                    "after_folder": after_folder,
                    "matched_tokens": list(judgment.matched_mechanism_tokens or []),
                    "reason": judgment.reason,
                }
            )

            logger.info(
                f"({i}/{len(papers)}) {(paper.title or '')[:60]}  "
                f"{before_score}→{judgment.score}  "
                f"{before_folder}→{after_folder}"
            )

            # dry-run: 일체의 DB 변경 없음
            if args.dry_run:
                continue

            paper.relevance_score = judgment.score
            paper.relevance_reason = judgment.reason
            paper.relevance_checked_at = datetime.now(timezone.utc)
            if after_bucket == "trash":
                paper.is_trashed = True
                paper.trashed_at = datetime.now(timezone.utc)
                paper.trash_reason = "phase_d_v2_recalibration"
            else:
                paper.is_trashed = False
                paper.trashed_at = None
                paper.trash_reason = None
            reassign_folder(db, paper, folder_ids[after_bucket], system_folder_ids)
            db.commit()

        # 새 agent_runs row (dry-run 시 생략)
        if not args.dry_run:
            run = AgentRun(
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                topic_snapshot=f"PHASE_D_V2_RECALIBRATION[{collection.name}]: {topic}",
                keywords_used=json.dumps(
                    ["phase_d_v2_recalibration", f"collection:{collection.name}"],
                    ensure_ascii=False,
                ),
                candidates_fetched=len(papers),
                new_papers=0,
                saved_papers=sum(1 for d in decisions if d["after_score"] is not None),
                trashed_papers=sum(
                    1 for d in decisions if d["after_folder"] == FOLDER_NAMES["trash"]
                ),
                recommended_papers=sum(
                    1 for d in decisions if d["after_folder"] == FOLDER_NAMES["full"]
                ),
                is_dry_run=0,
                error="\n".join(errors) if errors else None,
                duration_seconds=time.time() - t0,
                decisions_json=json.dumps(decisions, ensure_ascii=False),
            )
            db.add(run)
            db.commit()
            logger.info(f"agent_runs 새 row 기록 완료 (run.id={run.id})")

        write_diff_md(decisions, args, collection.name, ts, backup_path)

        succ = sum(1 for d in decisions if d["after_score"] is not None)
        logger.info(
            f"완료. 성공 {succ}건, 실패 {len(errors)}건, "
            f"{time.time() - t0:.1f}s, mode={'DRY RUN' if args.dry_run else 'COMMIT'}"
        )
        return 0
    finally:
        db.close()


def write_diff_md(
    decisions: List[dict],
    args: argparse.Namespace,
    collection_name: str,
    ts: str,
    backup_path: Optional[Path],
) -> None:
    out_path = PROJECT_ROOT / "docs" / f"CALIBRATION_DIFF_{collection_name}_{ts}.md"
    out_path.parent.mkdir(exist_ok=True, parents=True)

    def delta(d: dict) -> int:
        if d["after_score"] is None or d["before_score"] is None:
            return -999
        return abs(d["after_score"] - d["before_score"])

    decisions_sorted = sorted(decisions, key=delta, reverse=True)

    succ = sum(1 for d in decisions if d["after_score"] is not None)
    fail = sum(1 for d in decisions if d["after_score"] is None)

    lines = [
        f"# Phase D v2 — Calibration Diff ({collection_name})",
        "",
        f"실행: {datetime.now(timezone.utc).isoformat()}Z  "
        f"({'DRY RUN' if args.dry_run else 'COMMIT'})",
        f"collection: **{collection_name}**",
        f"총 {len(decisions)}건 (성공 {succ}, 실패 {fail})",
        f"백업: {backup_path if backup_path else '(dry-run, 백업 생략)'}",
        "",
        "변화량 큰 순으로 정렬. before_score는 기존 `papers.relevance_score`, "
        "before_folder는 매핑된 시스템 폴더, after_*는 RELEVANCE_SYSTEM v2 평가 결과.",
        "",
        "| 제목 | 이전 점수 | 이전 폴더 | 신규 점수 | 신규 폴더 | Δ | matched_tokens | reason |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for d in decisions_sorted:
        title = (d["title"] or "").replace("|", "/")[:80]
        before_s = "-" if d["before_score"] is None else str(d["before_score"])
        before_f = d["before_folder"] or "-"
        after_s = "-" if d["after_score"] is None else str(d["after_score"])
        after_f = d["after_folder"] or "-"
        if d["after_score"] is not None and d["before_score"] is not None:
            delta_str = f"{d['after_score'] - d['before_score']:+d}"
        else:
            delta_str = "-"
        tokens = ", ".join(d["matched_tokens"][:5]) if d["matched_tokens"] else "-"
        reason = (d["reason"] or "").replace("|", "/")[:120]
        lines.append(
            f"| {title} | {before_s} | {before_f} | {after_s} | {after_f} | "
            f"{delta_str} | {tokens} | {reason} |"
        )

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info(f"CALIBRATION_DIFF 작성: {out_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase D v2 — collection-격리 재캘리브레이션",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default=None,
        help="필수. 처리할 collection 이름 (예: CF4). 미지정 시 에러로 종료.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB 변경 없이 CALIBRATION_DIFF 만 작성",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="처리할 논문 개수 제한 (smoke test 용)",
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="평가 주제 override (기본: CF₄ Lewis acid)",
    )
    args = parser.parse_args()

    if not args.collection:
        print(
            "ERROR: --collection is required (e.g., --collection CF4)",
            file=sys.stderr,
        )
        return 1

    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
