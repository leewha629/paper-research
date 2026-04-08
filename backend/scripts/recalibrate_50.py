"""[DEPRECATED — Phase D v2로 교체됨. 신규 호출 금지.]

이 스크립트는 collection 필터가 없어서 multi-project 환경 (CF4, CPN/CPL, AI/3D 등)
에서 다른 도메인 자료를 CF4 RELEVANCE_SYSTEM으로 평가해 오분류하는 사고를 유발한다.
사양: .claude/prompts/refactor_score_calibration_v2.md 참고.

후속 스크립트: backend/scripts/recalibrate.py (--collection 필수 인자)
사용 예:
    ../venv/bin/python -m scripts.recalibrate --collection CF4 --dry-run
    ../venv/bin/python -m scripts.recalibrate --collection CF4

본 파일은 안전을 위해 **삭제하지 않고** 보존한다 (기존 백업/감사 추적용).
새로 호출하지 말 것.

----- 원본 docstring -----

Phase D — 저장된 50건 baseline 재분석 스크립트.

Step 4 (refactor_score_calibration.md):
- discovery.score_relevance를 새 RELEVANCE_SYSTEM 프롬프트로 호출
- 결과는 agent_runs에 새 row로 기록 (기존 row 덮어쓰기 금지)
- paper.relevance_score 업데이트, 임계값(7/5/4)에 맞춰 folder_papers 재배치
- docs/CALIBRATION_DIFF.md에 before/after 표 출력

사용:
    cd backend
    ../venv/bin/python -m scripts.recalibrate_50            # 기본 50건 재분석
    ../venv/bin/python -m scripts.recalibrate_50 --dry-run  # DB 변경 없이 표만 출력
    ../venv/bin/python -m scripts.recalibrate_50 --limit 10 # 10건만 (smoke test)
    ../venv/bin/python -m scripts.recalibrate_50 --topic "..."  # 주제 override

전제:
- ollama가 실행 중이고 gemma4:e4b 모델이 로드 가능해야 한다.
- data/papers.db가 backend/ 부모 경로에 존재해야 한다.

금지 (spec):
- 기존 agent_runs row 덮어쓰기 금지 → 항상 새 row insert
- paper.relevance_score는 갱신하되 paper.relevance_reason도 함께 갱신
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# backend/를 sys.path에 추가
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy.orm import Session

from database import SessionLocal
from models import AgentRun, FolderPaper, Folder, Paper
from services.llm import RelevanceJudgment, StrictCallError
from services.llm.tasks import score_relevance

logger = logging.getLogger("recalibrate_50")
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")

# Phase D 임계값 (refactor_score_calibration.md Step 4)
# 7/5/4 — ≥7 풀분석 추천 / ≥5 자동 발견 / ==4 검토 대기 / ≤3 휴지통
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


def load_target_papers(db: Session, limit: Optional[int]) -> List[Paper]:
    """50건 baseline = papers 테이블 전체 (휴지통 포함). 정렬은 paper.id."""
    q = db.query(Paper).order_by(Paper.id.asc())
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


def reassign_folder(db: Session, paper: Paper, target_folder_id: int) -> None:
    """해당 paper의 모든 folder_papers 매핑 중 시스템 폴더(풀분석/자동/검토/휴지통)만 갱신.

    CF4 같은 사용자 컬렉션 폴더는 건드리지 않는다 — folders에 is_system_folder가 있지만,
    여기서는 단순히 4개 시스템 폴더 ID에 해당하는 행만 삭제 후 재삽입한다.
    """
    system_ids = set(load_folder_ids(db).values())
    db.query(FolderPaper).filter(
        FolderPaper.paper_id == paper.id,
        FolderPaper.folder_id.in_(system_ids),
    ).delete(synchronize_session=False)
    db.add(FolderPaper(folder_id=target_folder_id, paper_id=paper.id))


async def recalibrate_one(
    paper: Paper,
    topic: str,
) -> tuple[Optional[RelevanceJudgment], Optional[str]]:
    """단일 논문 재평가. 실패 시 (None, error_msg)."""
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
    started_at = datetime.utcnow()
    t0 = time.time()
    decisions: List[dict] = []
    errors: List[str] = []

    try:
        papers = load_target_papers(db, limit=args.limit)
        logger.info(f"대상 논문 {len(papers)}건 로드")

        folder_ids = load_folder_ids(db)
        topic = args.topic or DEFAULT_TOPIC

        for i, paper in enumerate(papers, 1):
            before_score = paper.relevance_score
            before_folder = current_system_folder_name(db, paper.id, folder_ids)

            judgment, err = await recalibrate_one(paper, topic)
            if judgment is None:
                errors.append(f"[{paper.id}] {err}")
                logger.warning(f"({i}/{len(papers)}) {paper.title[:60]}: 실패 — {err}")
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
                f"({i}/{len(papers)}) {paper.title[:60]}  "
                f"{before_score}→{judgment.score}  "
                f"{before_folder}→{after_folder}"
            )

            if not args.dry_run:
                paper.relevance_score = judgment.score
                paper.relevance_reason = judgment.reason
                paper.relevance_checked_at = datetime.utcnow()
                paper.is_trashed = (after_bucket == "trash")
                if after_bucket == "trash":
                    paper.trashed_at = datetime.utcnow()
                    paper.trash_reason = "phase_d_recalibration"
                else:
                    paper.is_trashed = False
                    paper.trashed_at = None
                    paper.trash_reason = None
                reassign_folder(db, paper, folder_ids[after_bucket])
                db.commit()

        # 새 agent_runs row 기록 (기존 row 덮어쓰기 금지)
        if not args.dry_run:
            run = AgentRun(
                started_at=started_at,
                finished_at=datetime.utcnow(),
                topic_snapshot=f"PHASE_D_RECALIBRATION: {topic}",
                keywords_used=json.dumps(["phase_d_recalibration"], ensure_ascii=False),
                candidates_fetched=len(papers),
                new_papers=0,
                saved_papers=sum(1 for d in decisions if d["after_score"] is not None),
                trashed_papers=sum(
                    1
                    for d in decisions
                    if d["after_folder"] == FOLDER_NAMES["trash"]
                ),
                recommended_papers=sum(
                    1
                    for d in decisions
                    if d["after_folder"] == FOLDER_NAMES["full"]
                ),
                is_dry_run=0,
                error="\n".join(errors) if errors else None,
                duration_seconds=time.time() - t0,
                decisions_json=json.dumps(decisions, ensure_ascii=False),
            )
            db.add(run)
            db.commit()
            logger.info(f"agent_runs 새 row 기록 완료 (run.id={run.id})")

        # CALIBRATION_DIFF.md 출력
        write_diff_md(decisions, args)

        logger.info(
            f"완료. 성공 {sum(1 for d in decisions if d['after_score'] is not None)}건, "
            f"실패 {len(errors)}건, {time.time() - t0:.1f}s"
        )
        return 0
    finally:
        db.close()


def current_system_folder_name(
    db: Session, internal_paper_id: int, folder_ids: dict[str, int]
) -> Optional[str]:
    id_to_name = {v: k for k, v in folder_ids.items()}
    rows = (
        db.query(FolderPaper)
        .filter(FolderPaper.paper_id == internal_paper_id)
        .all()
    )
    for fp in rows:
        if fp.folder_id in id_to_name:
            return FOLDER_NAMES[id_to_name[fp.folder_id]]
    return None


def write_diff_md(decisions: List[dict], args: argparse.Namespace) -> None:
    out_path = BACKEND_DIR.parent / "docs" / "CALIBRATION_DIFF.md"
    out_path.parent.mkdir(exist_ok=True, parents=True)

    # 변화량 큰 순으로 정렬
    def delta(d: dict) -> int:
        if d["after_score"] is None or d["before_score"] is None:
            return -999
        return abs(d["after_score"] - d["before_score"])

    decisions_sorted = sorted(decisions, key=delta, reverse=True)

    lines = [
        "# Phase D — Calibration Diff",
        "",
        f"실행: {datetime.utcnow().isoformat()}Z  "
        f"({'DRY RUN' if args.dry_run else 'COMMIT'})",
        f"총 {len(decisions)}건 (실패 {sum(1 for d in decisions if d['after_score'] is None)}건)",
        "",
        "변화량 큰 순으로 정렬. before_score는 기존 `papers.relevance_score`, "
        "before_folder는 매핑된 시스템 폴더, after_*는 새 RELEVANCE_SYSTEM 평가 결과.",
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
    logger.info(f"CALIBRATION_DIFF.md 작성: {out_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase D 50건 재분석")
    parser.add_argument("--dry-run", action="store_true", help="DB 변경 없이 표만 출력")
    parser.add_argument("--limit", type=int, default=None, help="처리할 논문 개수 제한")
    parser.add_argument("--topic", type=str, default=None, help="주제 override")
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
