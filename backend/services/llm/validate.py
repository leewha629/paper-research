"""
Strict 클라이언트 형식 준수율 검증 스크립트.

CF4 주제로 가상 논문 fixture를 만들어 각 작업을 N회씩 호출하고:
- 성공률 (Pydantic 검증 통과)
- 평균 응답 시간
- 재시도 횟수 분포
- 실패 케이스 raw 응답

을 보고한다.

사용:
    python -m services.llm.validate                  # 기본 100회
    python -m services.llm.validate --runs 30        # 30회로 빠르게
    python -m services.llm.validate --task relevance # relevance만
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import List

# logging은 WARNING 이상만 (시도/재시도 노이즈 줄임)
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

# stdout 캡처를 위한 재시도 카운터 (전역, 단순)
RETRY_LOG: List[int] = []


# ==============================================================================
# Fixture: CF4 분해 촉매 주제로 다양한 점수가 나올만한 가상 논문들
# ==============================================================================

TOPIC = "CF4 분해 촉매와 반응 메커니즘 연구"

PAPER_FIXTURES = [
    # 명확히 관련 (예상 7~9)
    {
        "title": "Catalytic decomposition of CF4 over Al2O3 at moderate temperatures",
        "abstract": "We investigated the catalytic destruction of tetrafluoromethane over alumina catalysts at 500-700°C. CF4 conversion reached 95% at 650°C with stable activity over 50h. The reaction mechanism involves surface fluorination of Al2O3, forming AlF3 intermediates verified by XRD and XPS. A reaction pathway via dissociative adsorption is proposed.",
        "expected_band": "high",  # 7-9
    },
    {
        "title": "Plasma-assisted CF4 abatement using Ni-based catalysts",
        "abstract": "DBD plasma combined with Ni/Al2O3 catalyst destroys CF4 at low temperatures. Conversion of 88% achieved at 200°C with 1000 ppm CF4 in N2. In-situ FTIR shows CF3 radicals as key intermediates. Reactor design and residence time effects are discussed.",
        "expected_band": "high",
    },
    {
        "title": "Mechanism of CF4 thermal decomposition on metal oxide surfaces",
        "abstract": "DFT calculations and microkinetic modeling reveal the elementary steps of CF4 dissociation on MgO, Al2O3, and CaO surfaces. Activation energies and reaction pathways are reported. Comparison with experimental conversion data validates the mechanism.",
        "expected_band": "high",
    },
    # 인접 (예상 4~6)
    {
        "title": "DFT study of CF4 adsorption on transition metal surfaces",
        "abstract": "We compute adsorption energies and binding configurations of CF4 on Pt, Pd, and Rh surfaces. Charge transfer and bond elongation patterns are analyzed.",
        "expected_band": "mid",  # 4-6
    },
    {
        "title": "Fluorocarbon emissions from semiconductor etch processes",
        "abstract": "Survey of perfluorocarbon (CF4, C2F6, SF6) emissions from semiconductor manufacturing. CF4 is the dominant contributor. We discuss emission inventory and abatement options including thermal decomposition.",
        "expected_band": "mid",
    },
    # 무관 (예상 1~3)
    {
        "title": "Climate impact of perfluorinated greenhouse gases",
        "abstract": "PFCs have 100-year GWP up to 9000. We review atmospheric lifetimes of CF4, SF6 and discuss policy responses.",
        "expected_band": "low",  # 1-3
    },
    {
        "title": "Synthesis of cyclopentanone from furfural over Cu catalysts",
        "abstract": "Selective hydrogenation of biomass-derived furfural to cyclopentanone using Cu/Al2O3 in aqueous phase. Yield of 85% at 160°C.",
        "expected_band": "low",
    },
    {
        "title": "Lithium-ion battery anode materials review",
        "abstract": "Recent advances in graphite, silicon, and Li metal anodes. SEI formation and cycle stability are discussed.",
        "expected_band": "low",
    },
]


@dataclass
class TaskResult:
    name: str
    runs: int
    successes: int = 0
    failures: int = 0
    durations: List[float] = field(default_factory=list)
    score_distribution: dict = field(default_factory=dict)  # relevance only
    failure_examples: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return self.successes / self.runs * 100 if self.runs else 0.0

    @property
    def avg_duration(self) -> float:
        return statistics.mean(self.durations) if self.durations else 0.0

    @property
    def median_duration(self) -> float:
        return statistics.median(self.durations) if self.durations else 0.0


# ==============================================================================
# 검증: Role 1 - 키워드 생성
# ==============================================================================

async def validate_keywords(runs: int) -> TaskResult:
    from services.llm import extract_keywords, StrictCallError

    result = TaskResult(name="extract_keywords", runs=runs)
    print(f"\n[Role 1] 키워드 생성 — {runs}회")

    for i in range(runs):
        # 매번 exclude 목록 다르게 (다양성 강제 테스트)
        exclude = [] if i % 3 == 0 else ["CF4 decomposition catalyst", "PFC abatement"]
        t0 = time.time()
        try:
            kw = await extract_keywords(TOPIC, exclude=exclude)
            elapsed = time.time() - t0
            result.successes += 1
            result.durations.append(elapsed)
            print(f"  ✓ #{i+1:3d} [{elapsed:5.2f}s] {len(kw.keywords)}개: {kw.keywords[:2]}...")
        except StrictCallError as e:
            elapsed = time.time() - t0
            result.failures += 1
            result.durations.append(elapsed)
            print(f"  ✗ #{i+1:3d} [{elapsed:5.2f}s] FAIL: {e}")
            if len(result.failure_examples) < 3 and e.last_raw:
                result.failure_examples.append(e.last_raw[:300])

    return result


# ==============================================================================
# 검증: Role 2 - 관련도 평가
# ==============================================================================

async def validate_relevance(runs: int) -> TaskResult:
    from services.llm import score_relevance, StrictCallError

    result = TaskResult(name="score_relevance", runs=runs)
    print(f"\n[Role 2] 관련도 평가 — {runs}회 (fixture {len(PAPER_FIXTURES)}개 순환)")

    band_check = {"high": [], "mid": [], "low": []}

    for i in range(runs):
        paper = PAPER_FIXTURES[i % len(PAPER_FIXTURES)]
        t0 = time.time()
        try:
            j = await score_relevance(TOPIC, paper["title"], paper["abstract"])
            elapsed = time.time() - t0
            result.successes += 1
            result.durations.append(elapsed)
            result.score_distribution[j.score] = result.score_distribution.get(j.score, 0) + 1
            band_check[paper["expected_band"]].append(j.score)
            print(f"  ✓ #{i+1:3d} [{elapsed:5.2f}s] score={j.score} ({paper['expected_band']:>4s}): {j.reason[:60]}")
        except StrictCallError as e:
            elapsed = time.time() - t0
            result.failures += 1
            result.durations.append(elapsed)
            print(f"  ✗ #{i+1:3d} [{elapsed:5.2f}s] FAIL: {e}")
            if len(result.failure_examples) < 3 and e.last_raw:
                result.failure_examples.append(e.last_raw[:300])

    # 점수 밴드 정확도 (참고용)
    print(f"\n  밴드별 점수 평균:")
    for band, scores in band_check.items():
        if scores:
            avg = statistics.mean(scores)
            print(f"    {band:>4s} (예상 {('7-9','4-6','1-3')[['high','mid','low'].index(band)]}): "
                  f"실제 평균 {avg:.1f}, n={len(scores)}, 분포={sorted(set(scores))}")

    return result


# ==============================================================================
# 검증: Role 3 - 요약
# ==============================================================================

async def validate_summary(runs: int) -> TaskResult:
    from services.llm import summarize, StrictCallError

    result = TaskResult(name="summarize", runs=runs)
    print(f"\n[Role 3] 요약 — {runs}회")

    for i in range(runs):
        paper = PAPER_FIXTURES[i % len(PAPER_FIXTURES)]
        t0 = time.time()
        try:
            s = await summarize(paper["title"], paper["abstract"])
            elapsed = time.time() - t0
            result.successes += 1
            result.durations.append(elapsed)
            print(f"  ✓ #{i+1:3d} [{elapsed:5.2f}s] terms={len(s.key_terms)}, summary[:50]={s.summary_kr[:50]}...")
        except StrictCallError as e:
            elapsed = time.time() - t0
            result.failures += 1
            result.durations.append(elapsed)
            print(f"  ✗ #{i+1:3d} [{elapsed:5.2f}s] FAIL: {e}")
            if len(result.failure_examples) < 3 and e.last_raw:
                result.failure_examples.append(e.last_raw[:300])

    return result


# ==============================================================================
# 보고서
# ==============================================================================

def print_summary(results: List[TaskResult]) -> None:
    print("\n" + "=" * 70)
    print("검증 결과 요약")
    print("=" * 70)
    total_success = sum(r.successes for r in results)
    total_runs = sum(r.runs for r in results)
    overall = total_success / total_runs * 100 if total_runs else 0

    for r in results:
        print(
            f"\n{r.name:25s}: {r.successes:3d}/{r.runs:3d} "
            f"({r.success_rate:5.1f}%)  "
            f"avg={r.avg_duration:.2f}s  median={r.median_duration:.2f}s"
        )
        if r.score_distribution:
            print(f"  점수 분포: {dict(sorted(r.score_distribution.items()))}")
        if r.failure_examples:
            print(f"  실패 raw 예시 ({len(r.failure_examples)}):")
            for raw in r.failure_examples:
                print(f"    | {raw[:200]}")

    print()
    print(f"{'='*70}")
    print(f"전체: {total_success}/{total_runs} = {overall:.1f}%")
    if overall >= 99:
        print("판정: ✅ 합격 (>=99%) — Phase 2 진행 가능")
    elif overall >= 95:
        print("판정: ⚠️  경계 (95~99%) — 재시도/프롬프트 보강 검토")
    else:
        print("판정: ❌ 불합격 (<95%) — 추가 방어선 필요 또는 모델 변경 검토")
    print("=" * 70)


# ==============================================================================
# 엔트리
# ==============================================================================

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=100, help="총 호출 수 (작업별로 분배)")
    parser.add_argument(
        "--task",
        choices=["all", "keywords", "relevance", "summary"],
        default="all",
    )
    args = parser.parse_args()

    runs_per_task = args.runs // 3 if args.task == "all" else args.runs

    print(f"검증 시작: {args.task} × {runs_per_task}회")
    print(f"주제: {TOPIC}")
    t_start = time.time()

    results = []
    if args.task in ("all", "keywords"):
        results.append(await validate_keywords(runs_per_task))
    if args.task in ("all", "relevance"):
        results.append(await validate_relevance(runs_per_task))
    if args.task in ("all", "summary"):
        results.append(await validate_summary(runs_per_task))

    print_summary(results)
    print(f"\n총 소요: {time.time() - t_start:.1f}s")


if __name__ == "__main__":
    # backend 디렉토리를 sys.path에 추가
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    backend = os.path.normpath(os.path.join(here, "..", ".."))
    sys.path.insert(0, backend)

    asyncio.run(main())
