"""정적 샘플 논문 픽스처.

PLAN §A.1 — CF₄/할로겐/VOC 인접 5건 + 무관 5건.
PLAN §"멀티 프로젝트 고려" — 분야 태그(field)를 함께 보유.

Phase D의 캘리브레이션 통합 테스트(#22~#25)가 같은 데이터를 재사용한다.
Phase A에서는 데이터 구조만 준비하고, 실제 점수 검증은 하지 않는다.
"""
from __future__ import annotations


# 분야 태그: "CF4" / "halogen" / "VOC" / "AI" / "3D" / "unrelated"
SAMPLE_PAPERS: list[dict] = [
    # ─── CF₄ 인접 (2건) ─────────────────────────────────────────────
    {
        "paperId": "cf4-001",
        "title": "Plasma abatement of CF4 in semiconductor exhaust streams",
        "abstract": (
            "We report a non-thermal plasma reactor for CF4 destruction in "
            "semiconductor process exhaust. The system achieves 95% removal "
            "at 800 W input power."
        ),
        "year": 2024,
        "venue": "Journal of Hazardous Materials",
        "authors": [{"name": "Lee, S."}],
        "field": "CF4",
    },
    {
        "paperId": "cf4-002",
        "title": "Catalytic hydrolysis of NF3 and CF4 over Al2O3-based sorbents",
        "abstract": (
            "Comparative study of perfluorocompound abatement using alumina "
            "sorbents at 600-800 C."
        ),
        "year": 2023,
        "venue": "Chemical Engineering Journal",
        "authors": [{"name": "Park, J."}],
        "field": "CF4",
    },
    # ─── 할로겐 인접 (2건) ──────────────────────────────────────────
    {
        "paperId": "halogen-001",
        "title": "Halogen scavenging in fluorinated greenhouse gas decomposition",
        "abstract": (
            "Mechanistic insights into HF and F2 capture downstream of "
            "thermal abatement units."
        ),
        "year": 2023,
        "venue": "Environmental Science & Technology",
        "authors": [{"name": "Kim, H."}],
        "field": "halogen",
    },
    {
        "paperId": "halogen-002",
        "title": "Photocatalytic degradation of perfluorinated compounds",
        "abstract": "TiO2-based photocatalysts for PFC removal under UV irradiation.",
        "year": 2022,
        "venue": "Applied Catalysis B",
        "authors": [{"name": "Choi, M."}],
        "field": "halogen",
    },
    # ─── VOC 인접 (1건) ─────────────────────────────────────────────
    {
        "paperId": "voc-001",
        "title": "Plasma-catalytic VOC abatement using Mn-based catalysts",
        "abstract": (
            "Non-thermal plasma combined with MnO2 for toluene decomposition "
            "at low temperatures."
        ),
        "year": 2024,
        "venue": "Catalysis Today",
        "authors": [{"name": "Yoon, K."}],
        "field": "VOC",
    },
    # ─── 무관 (5건) ─────────────────────────────────────────────────
    {
        "paperId": "unrel-001",
        "title": "Deep learning for protein folding prediction",
        "abstract": "Transformer-based architecture for predicting tertiary structures.",
        "year": 2024,
        "venue": "Nature",
        "authors": [{"name": "Smith, A."}],
        "field": "AI",
    },
    {
        "paperId": "unrel-002",
        "title": "3D-printed scaffolds for bone tissue engineering",
        "abstract": "Biocompatible PLA scaffolds with graded porosity.",
        "year": 2023,
        "venue": "Biomaterials",
        "authors": [{"name": "Tanaka, R."}],
        "field": "3D",
    },
    {
        "paperId": "unrel-003",
        "title": "Reinforcement learning for autonomous driving",
        "abstract": "Policy gradient methods applied to lane-keeping tasks.",
        "year": 2024,
        "venue": "ICML",
        "authors": [{"name": "Garcia, P."}],
        "field": "AI",
    },
    {
        "paperId": "unrel-004",
        "title": "Fluorine NMR spectroscopy for drug discovery",
        "abstract": (
            "19F NMR techniques for screening fluorinated drug candidates. "
            "Note: 'fluorine' 키워드가 등장하지만 분야는 의약화학."
        ),
        "year": 2022,
        "venue": "Journal of Medicinal Chemistry",
        "authors": [{"name": "Brown, L."}],
        "field": "unrelated",  # 함정 케이스: 키워드는 있지만 분야 무관
    },
    {
        "paperId": "unrel-005",
        "title": "Quantum entanglement in photonic systems",
        "abstract": "Bell state generation using parametric down-conversion.",
        "year": 2023,
        "venue": "Physical Review Letters",
        "authors": [{"name": "Watanabe, T."}],
        "field": "unrelated",
    },
]


def papers_by_field(field: str) -> list[dict]:
    """분야 태그로 필터링."""
    return [p for p in SAMPLE_PAPERS if p["field"] == field]


def relevant_papers() -> list[dict]:
    """CF4 / halogen / VOC 인접 5건."""
    return [p for p in SAMPLE_PAPERS if p["field"] in {"CF4", "halogen", "VOC"}]


def unrelated_papers() -> list[dict]:
    """무관 5건 (AI / 3D / 함정 포함)."""
    return [p for p in SAMPLE_PAPERS if p["field"] in {"AI", "3D", "unrelated"}]
