"""Phase D — RELEVANCE_SYSTEM 캘리브레이션 통합 테스트 (#22~#25).

PLAN §A.2 "Phase D 종료 시 추가 (4건)" — 실제 ollama를 호출하므로 @pytest.mark.integration.

실행:
    cd backend
    ../venv/bin/python -m pytest -m integration -q          # 통합만
    ../venv/bin/python -m pytest -m "not integration" -q    # 통합 제외 (CI 기본)

전제:
- ollama가 localhost:11434에서 실행 중
- gemma4:e4b 모델이 로드 가능

검증 분포 (PAPER_TRIAGE 50건 baseline에서 선별):
- 직접 일치 5건 → 점수 ≥8 기대
- 인접 5건     → 점수 5~7 기대 (감점 1점 허용 → ≥4)
- 무관 5건     → 점수 ≤3 기대

각 테스트는 그룹 단위로 평균/최솟값/최댓값을 검증한다.
개별 논문이 ±1점 흔들려도 그룹 통계가 기대 범위에 들면 PASS — 작은 모델의 출력
변동성을 흡수.
"""
from __future__ import annotations

import asyncio
from statistics import mean

import pytest

from services.llm.tasks import score_relevance


TOPIC = "CF₄ catalytic decomposition / hydrolysis (Lewis acid Al/Zr/Ga/W/Ce 산화물)"


# ─────────────────────────────────────────────────────────────────────────
# Fixture: PAPER_TRIAGE 50건에서 분야 태그별로 선별
# ─────────────────────────────────────────────────────────────────────────

DIRECT_PAPERS = [
    {
        "title": "Catalytic thermal decomposition of tetrafluoromethane (CF4): A review",
        "abstract": (
            "This review summarizes the catalytic-thermal decomposition studies present "
            "for tetrafluoromethane. Tetrafluoromethane (CF4, R-14) possesses a GWP of "
            "6,630 and has a lifetime of 50,000 years."
        ),
    },
    {
        "title": (
            "Highly Efficient Decomposition of Perfluorocarbons for over 1000 Hours via "
            "Active Site Regeneration"
        ),
        "abstract": (
            "Tetrafluoromethane (CF4), the simplest perfluorocarbon (PFC), has the "
            "potential to exacerbate global warming. Catalytic hydrolysis is a viable "
            "method to degrade CF4, but fluorine poisoning severely restricts both the "
            "catalytic performance and catalyst lifetime."
        ),
    },
    {
        "title": (
            "Optimization of Sol–Gel Catalysts with Zirconium and Tungsten Additives for "
            "Enhanced CF4 Decomposition Performance"
        ),
        "abstract": (
            "This study investigated the development and optimization of sol–gel "
            "synthesized Ni/ZrO2-Al2O3 catalysts, aiming to enhance the decomposition "
            "efficiency of CF4, a potent greenhouse gas. The research focused on "
            "improving catalytic performance at temperatures below 700 °C by "
            "incorporating zirconium and tungsten."
        ),
    },
    {
        "title": (
            "The Zr Modified γ-Al2O3 Catalysts for Stable Hydrolytic Decomposition of "
            "CF4 at Low Temperature"
        ),
        "abstract": (
            "CF4, one of the Perfluorocompounds (PFCs), also known as a greenhouse gas "
            "with high global warming potential. In this study, Zr/γ-Al2O3 catalysts "
            "were developed for CF4 decomposition."
        ),
    },
    {
        "title": (
            "Hydrolytic decomposition of CF4 over alumina-based binary metal oxide "
            "catalysts: high catalytic activity of gallia-alumina catalyst"
        ),
        "abstract": (
            "Gallia-alumina binary metal oxide catalysts show very high CF4 hydrolytic "
            "decomposition activity. Lewis acid sites on Ga-Al composite oxide enable "
            "C-F bond activation."
        ),
    },
]

ADJACENT_PAPERS = [
    {
        "title": (
            "Hydrolysis of Hexafluoroethane (PFC-116) over Alumina–zirconia Catalysts "
            "Prepared from γ-Alumina and Boehmite"
        ),
        "abstract": (
            "C2F6 (PFC-116) catalytic hydrolysis over Al2O3-ZrO2 catalysts. Same "
            "Lewis acid hydrolysis mechanism as CF4 decomposition."
        ),
    },
    {
        "title": (
            "H-zeolite supported multi-interface metal catalysts for the catalytic "
            "destruction of chlorinated organics"
        ),
        "abstract": (
            "H-zeolite based catalysts for chlorinated VOC destruction. Halogen "
            "activation via acid sites discussed."
        ),
    },
    {
        "title": "Preliminary Study on Plasma-Catalyst Combination for CF4 Removal",
        "abstract": (
            "DBD plasma combined with metal oxide catalyst for CF4 abatement at low "
            "temperature. Plasma-catalyst synergy is investigated."
        ),
    },
    {
        "title": "The Design of Sulfated Ce/HZSM-5 for Catalytic Decomposition of CF4",
        "abstract": (
            "CF4 has a global warming potential of 6500 and possesses a lifetime of "
            "50,000 years. In this study, we modified the HZSM-5 catalyst with Ce and "
            "sulfuric acid treatment for catalytic CF4 decomposition."
        ),
    },
    {
        "title": (
            "Boosted 1,3-dichlorobenzene catalytic destruction over P-Co-LaCoO3 by "
            "rational engineering"
        ),
        "abstract": (
            "Catalytic destruction of dichlorobenzene over P-Co-LaCoO3. Cl-VOC "
            "abatement via Co-La perovskite catalyst."
        ),
    },
]

UNRELATED_PAPERS = [
    {
        "title": (
            "Synthesis of the SrO–CaO–Al2O3 trimetallic oxide catalyst for "
            "transesterification to produce biodiesel"
        ),
        "abstract": (
            "Calcium oxide is one of the most promising heterogeneous catalysts for "
            "biodiesel production via transesterification of vegetable oil."
        ),
    },
    {
        "title": (
            "Effective toluene oxidation under ozone over mesoporous MnOx/γ-Al2O3 "
            "catalyst"
        ),
        "abstract": (
            "MnOx/γ-Al2O3 catalysts for toluene oxidation under ozone at ambient "
            "temperature. The role of manganese precursors was studied."
        ),
    },
    {
        "title": (
            "Promoted adsorption of methyl mercaptan by γ-Al2O3 catalyst loaded with "
            "Cu/Mn"
        ),
        "abstract": (
            "γ-Al2O3 catalysts loaded with Fe, Cu, Mn, Co for room-temperature CH3SH "
            "removal via impregnation method."
        ),
    },
    {
        "title": (
            "Photo-catalytic destruction of tetracycline antibiotics using terbium and "
            "manganese co-precipitated TiO2 photocatalyst"
        ),
        "abstract": (
            "TiO2-based photocatalyst doped with Tb and Mn for tetracycline antibiotic "
            "removal from water under UV light."
        ),
    },
    {
        "title": "DFAMO/BAMO copolymer as a potential energetic binder: Thermal decomposition study",
        "abstract": (
            "Thermal decomposition properties of DFAMO/BAMO energetic copolymer as a "
            "binder material for solid propellants."
        ),
    },
]


# ─────────────────────────────────────────────────────────────────────────
# 헬퍼: 그룹 점수 수집
# ─────────────────────────────────────────────────────────────────────────


async def _collect_scores(papers: list[dict]) -> list[int]:
    scores: list[int] = []
    for p in papers:
        judgment = await score_relevance(TOPIC, p["title"], p["abstract"])
        scores.append(judgment.score)
    return scores


# ─── #22 ─────────────────────────────────────────────────────────────────
@pytest.mark.integration
@pytest.mark.asyncio
async def test_relevance_direct_match_high_scores():
    """직접 일치 5건은 평균 ≥8, 모두 ≥7 (작은 모델 ±1 흔들림 허용)."""
    scores = await _collect_scores(DIRECT_PAPERS)
    assert len(scores) == 5
    assert mean(scores) >= 8.0, f"평균 점수가 너무 낮음: {scores}, 평균 {mean(scores):.1f}"
    assert min(scores) >= 7, f"최저 점수 7 미만: {scores}"


# ─── #23 ─────────────────────────────────────────────────────────────────
@pytest.mark.integration
@pytest.mark.asyncio
async def test_relevance_adjacent_mid_scores():
    """인접 5건은 평균 5~7, 모두 4~8 범위."""
    scores = await _collect_scores(ADJACENT_PAPERS)
    assert len(scores) == 5
    avg = mean(scores)
    assert 5.0 <= avg <= 7.5, f"인접 평균 범위 이탈: {scores}, 평균 {avg:.1f}"
    assert all(4 <= s <= 8 for s in scores), f"인접 점수 범위 이탈: {scores}"


# ─── #24 ─────────────────────────────────────────────────────────────────
@pytest.mark.integration
@pytest.mark.asyncio
async def test_relevance_unrelated_low_scores():
    """무관 5건은 평균 ≤3, 모두 ≤4."""
    scores = await _collect_scores(UNRELATED_PAPERS)
    assert len(scores) == 5
    avg = mean(scores)
    assert avg <= 3.0, f"무관 평균이 너무 높음: {scores}, 평균 {avg:.1f}"
    assert max(scores) <= 4, f"무관 최댓값 4 초과: {scores}"


# ─── #25 ─────────────────────────────────────────────────────────────────
@pytest.mark.integration
@pytest.mark.asyncio
async def test_relevance_score_band_separation():
    """직접 평균 - 무관 평균 ≥ 5, 인접은 그 사이에 위치.

    캘리브레이션의 핵심: 분야 간 점수 분리도. ±1 흔들림이 있어도 분리도는 유지되어야 함.
    """
    direct = await _collect_scores(DIRECT_PAPERS)
    adjacent = await _collect_scores(ADJACENT_PAPERS)
    unrelated = await _collect_scores(UNRELATED_PAPERS)

    direct_avg = mean(direct)
    adjacent_avg = mean(adjacent)
    unrelated_avg = mean(unrelated)

    # 핵심 분리도
    assert direct_avg - unrelated_avg >= 5.0, (
        f"직접/무관 분리도 부족: direct={direct_avg:.1f}, unrelated={unrelated_avg:.1f}"
    )
    # 인접은 가운데에 있어야 함
    assert unrelated_avg < adjacent_avg < direct_avg, (
        f"인접 위치 이탈: direct={direct_avg:.1f}, adjacent={adjacent_avg:.1f}, "
        f"unrelated={unrelated_avg:.1f}"
    )
