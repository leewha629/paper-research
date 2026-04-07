"""
수동 트리거: 1 사이클 Discovery 실행 + 결과 표 출력.

사용:
    python -m services.run_agent_once                       # CF4 (기본), 실DB
    python -m services.run_agent_once --project CF4
    python -m services.run_agent_once --dry-run             # DB 변경 없이 분류만
    python -m services.run_agent_once --max-candidates 30   # 빠른 테스트

처음 실행 시 자동으로 CF4 프로젝트를 부트스트랩한다 (레지스트리 등록 + DB 생성 + 시스템 폴더 시드).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys


# ─── 패키지 경로 부트스트랩 (직접 실행 호환) ──────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.normpath(os.path.join(_HERE, ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


from services.research_agent import bootstrap_project, run_discovery_cycle


DEFAULT_PROJECT = "CF4"
DEFAULT_TOPIC = "CF4 분해 촉매와 반응 메커니즘 연구"


def _print_report(report) -> None:
    print()
    print("=" * 70)
    print(f"Discovery 결과 — {report.project}")
    print("=" * 70)
    print(f"  주제          : {report.topic}")
    print(f"  사용 키워드   : {len(report.keywords_used)}개")
    for kw in report.keywords_used:
        print(f"                  - {kw}")
    print(f"  S2 후보       : {report.candidates_fetched}건")
    print(f"  중복 제외 신규: {report.new_papers}건")
    print(f"  소요 시간     : {report.duration_seconds:.1f}s")
    print(f"  dry_run       : {report.is_dry_run}")
    print()
    print("  분류 결과:")
    print(f"    풀분석 추천 (7~9): {report.recommended:>3d}")
    print(f"    자동 발견   (5~6): {report.auto_saved:>3d}")
    print(f"    검토 대기    ( 4): {report.holding:>3d}")
    print(f"    휴지통      (0~3): {report.trashed:>3d}")
    print()
    if report.score_distribution:
        print(f"  점수 분포: {dict(sorted(report.score_distribution.items()))}")
    if report.errors:
        print(f"\n  ⚠️  오류 {len(report.errors)}건:")
        for e in report.errors[:5]:
            print(f"    - {e[:120]}")
    print()
    print("  결정 상세 (앞 15건):")
    for d in report.decisions[:15]:
        bucket_short = {"풀분석 추천": "★", "자동 발견": "+", "검토 대기": "?", "휴지통": "✗"}
        mark = bucket_short.get(d["bucket"], " ")
        print(f"    {mark} [{d['score']}] {d['title'][:70]}")
        print(f"       └ {d['reason'][:80]}")
    print("=" * 70)


async def amain():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--topic", default=DEFAULT_TOPIC, help="첫 부트스트랩 시 사용")
    parser.add_argument("--limit-per-query", type=int, default=10)
    parser.add_argument("--max-candidates", type=int, default=60)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"[1/2] 프로젝트 부트스트랩: {args.project}")
    handles = bootstrap_project(args.project, args.topic)
    print(f"      collection_id={handles.collection_id} parent_folder={handles.parent_folder_id}")
    print(f"      sub-folders={handles.folder_ids}")
    print(f"      주제: {args.topic}")

    print(f"\n[2/2] Discovery 1 사이클 실행 (dry_run={args.dry_run})…")
    report = await run_discovery_cycle(
        args.project,
        args.topic,
        limit_per_query=args.limit_per_query,
        max_candidates=args.max_candidates,
        dry_run=args.dry_run,
    )
    _print_report(report)


if __name__ == "__main__":
    asyncio.run(amain())
