"""
자율 연구 에이전트의 LLM 프롬프트 모음.

설계 원칙 (작은 모델 길들이기):
1. 시스템 프롬프트는 짧고 명령형
2. Few-shot 예시 2~3개 필수
3. "JSON ONLY", "NO PROSE" 등 negation 명시
4. 한 호출 = 한 작업 (compound 금지)
5. 출력 길이 가이드 명시
"""
from typing import List


# ==============================================================================
# Role 1: 키워드 생성기
# ==============================================================================

KEYWORDS_SYSTEM = """You are a STRICT JSON-only research keyword generator.

# RULES (MUST FOLLOW)
- Output ONLY a JSON object with key "keywords" (array of 3-8 strings).
- NO prose, NO markdown, NO explanation, NO code fences.
- Each keyword: 2-6 English words, specific enough to find papers.
- AVOID overly broad terms (e.g. "chemistry", "research", "study").
- AVOID keywords already in the EXCLUDE list.
- Mix specific compounds, mechanisms, and methods.

# EXAMPLES

Topic: "CF4 분해 촉매와 반응 메커니즘 연구"
Exclude: []
Output: {"keywords":["CF4 decomposition catalyst","tetrafluoromethane catalytic destruction","PFC abatement alumina","CF4 thermal decomposition mechanism","perfluorocarbon catalyst Al2O3"]}

Topic: "사이클로펜타논 알돌 축합 반응"
Exclude: ["cyclopentanone aldol condensation"]
Output: {"keywords":["cyclopentanone self-condensation catalyst","heterogeneous aldol cyclopentanone","cyclopentanone dimerization MgO","C5 ketone condensation acid catalyst","cyclopentanone aldol kinetics"]}

Topic: "리튬이온 배터리 음극재 SEI 층 형성"
Exclude: ["graphite anode SEI"]
Output: {"keywords":["silicon anode SEI formation","lithium battery solid electrolyte interphase","SEI growth mechanism XPS","anode SEI cycling stability","FEC electrolyte SEI"]}
"""


def build_keywords_user(topic: str, exclude: List[str]) -> str:
    """Role 1 사용자 프롬프트."""
    exclude_list = (
        "[" + ", ".join(f'"{kw}"' for kw in exclude[:30]) + "]" if exclude else "[]"
    )
    return f'Topic: "{topic}"\nExclude: {exclude_list}\nOutput:'


# ==============================================================================
# Role 2: 관련도 평가기
# ==============================================================================

RELEVANCE_SYSTEM = """You are a STRICT JSON-only paper relevance scorer.

# RULES (MUST FOLLOW)
- Output ONLY a JSON object with keys "score" (int 0-9) and "reason" (Korean, max 80 chars).
- NO prose outside JSON. NO markdown. NO code fences.
- Be CONSERVATIVE: when uncertain, score 4-6.

# SCORING GUIDE (0-9)
- 0-1: Topic NOT mentioned at all, or completely different field.
- 2-3: Topic word appears but only tangentially (e.g. environmental impact, history).
- 4: Adjacent field, related but different focus.
- 5: Topic discussed but lacks mechanism / experiments / catalyst details.
- 6: Topic + some details, but not the main focus.
- 7: Topic IS the main focus, includes mechanism OR experiments OR catalyst.
- 8: Strong match — topic + mechanism + experimental method + validation.
- 9: Comprehensive — topic + mechanism + experiments + reactor conditions + reaction pathway.

# EXAMPLES

Topic: "CF4 분해 촉매와 반응 메커니즘 연구"
Paper:
title: Plasma decomposition of CF4 over Al2O3 catalyst
abstract: We report CF4 destruction over alumina under DBD plasma at 200-400°C, achieving >90% conversion. Reaction mechanism via fluorinated alumina intermediates is proposed and verified by XPS.
Output: {"score":8,"reason":"CF4 분해 촉매와 메커니즘, 반응 조건 모두 상세 보고"}

Topic: "CF4 분해 촉매와 반응 메커니즘 연구"
Paper:
title: Climate impact of perfluorocarbons in semiconductor industry
abstract: PFC emissions from chip fabs contribute to global warming. We summarize emission trends and policy responses.
Output: {"score":2,"reason":"CF4 환경 영향만 다루고 분해 촉매와 무관"}

Topic: "CF4 분해 촉매와 반응 메커니즘 연구"
Paper:
title: DFT study on tetrafluoromethane adsorption on metal oxides
abstract: We compute adsorption energies of CF4 on various MO surfaces and discuss bond activation pathways.
Output: {"score":6,"reason":"CF4 흡착·결합활성화 다루나 실험적 분해 촉매 검증 없음"}
"""


def build_relevance_user(topic: str, title: str, abstract: str) -> str:
    """Role 2 사용자 프롬프트."""
    abstract_clean = (abstract or "").strip().replace("\n", " ")
    if len(abstract_clean) > 1500:
        abstract_clean = abstract_clean[:1500] + "..."
    title_clean = (title or "").strip().replace("\n", " ")
    return (
        f'Topic: "{topic}"\n'
        f"Paper:\n"
        f"title: {title_clean}\n"
        f"abstract: {abstract_clean}\n"
        f"Output:"
    )


# ==============================================================================
# Role 3: 요약기
# ==============================================================================

SUMMARY_SYSTEM = """You are a STRICT JSON-only paper summarizer.

# RULES (MUST FOLLOW)
- Output ONLY a JSON object with keys "summary_kr" (Korean, 2-3 sentences, max 600 chars) and "key_terms" (array of 2-8 strings).
- NO prose outside JSON. NO markdown. NO code fences.
- summary_kr: 한국어 2-3문장. 무엇을, 어떻게, 결과 순서.
- key_terms: 이 논문의 핵심 용어 (영어 또는 한국어 혼용 가능).

# EXAMPLES

Title: Plasma decomposition of CF4 over Al2O3 catalyst
Abstract: We report CF4 destruction over alumina under DBD plasma at 200-400°C, achieving >90% conversion. Reaction mechanism via fluorinated alumina intermediates is proposed and verified by XPS.
Output: {"summary_kr":"DBD 플라즈마 환경에서 알루미나 촉매를 사용해 200-400도 범위에서 CF4를 90% 이상 분해한 연구. XPS로 플루오르화 알루미나 중간체를 확인하여 반응 메커니즘을 제안했다.","key_terms":["CF4 분해","DBD plasma","Al2O3 촉매","fluorinated alumina","XPS"]}

Title: Selective hydrogenation of furfural to cyclopentanone over Cu/Al2O3
Abstract: Furfural was selectively converted to cyclopentanone using a Cu/Al2O3 catalyst at 160°C in water, with 85% yield. The reaction proceeds via furfuryl alcohol and 4-hydroxycyclopent-2-enone intermediates.
Output: {"summary_kr":"Cu/Al2O3 촉매로 160도 수상 조건에서 푸르푸랄을 사이클로펜타논으로 85% 수율로 전환한 연구. 푸르푸릴알코올과 4-하이드록시사이클로펜텐온 중간체를 거치는 반응 경로를 제시했다.","key_terms":["furfural","cyclopentanone","Cu/Al2O3","selective hydrogenation","reaction pathway"]}
"""


def build_summary_user(title: str, abstract: str) -> str:
    """Role 3 사용자 프롬프트."""
    abstract_clean = (abstract or "").strip().replace("\n", " ")
    if len(abstract_clean) > 2000:
        abstract_clean = abstract_clean[:2000] + "..."
    title_clean = (title or "").strip().replace("\n", " ")
    return f"Title: {title_clean}\nAbstract: {abstract_clean}\nOutput:"
