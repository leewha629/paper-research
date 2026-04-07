"""
LLM 응답 강제 스키마.

각 모델은 두 가지 역할:
1. Ollama format=<schema> 파라미터로 디코더에 전달 → grammar-constrained decoding
2. 응답 JSON을 Pydantic으로 검증 → 잘못된 출력 자동 거부 + 재시도

Pydantic v2의 model_json_schema()로 JSON Schema를 추출해 Ollama에 넘긴다.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class RelevanceJudgment(BaseModel):
    """관련도 평가 (Role 2: 점수 + 한국어 한 문장 이유)."""

    score: int = Field(
        ...,
        ge=0,
        le=9,
        description="0~9 정수. 0=완전 무관, 5=인접/주변, 7=정확히 일치+상세, 9=완벽",
    )
    reason: str = Field(
        ...,
        min_length=5,
        max_length=200,
        description="한국어 한 문장 이유 (최대 200자)",
    )

    @field_validator("reason")
    @classmethod
    def reason_no_newlines(cls, v: str) -> str:
        # 한 문장 강제 — 줄바꿈 제거
        return " ".join(v.split())


class KeywordList(BaseModel):
    """키워드 생성 (Role 1: 검색어 5개)."""

    keywords: List[str] = Field(
        ...,
        min_length=3,
        max_length=8,
        description="영어 검색 키워드 3~8개. 너무 광범위하지 않게.",
    )

    @field_validator("keywords")
    @classmethod
    def normalize_keywords(cls, v: List[str]) -> List[str]:
        cleaned = []
        seen = set()
        for kw in v:
            kw = " ".join(kw.split()).strip().lower()
            if not kw:
                continue
            if len(kw) < 3:  # 너무 짧은 단어 제외
                continue
            if len(kw) > 80:  # 너무 긴 문장 제외
                continue
            if kw in seen:
                continue
            seen.add(kw)
            cleaned.append(kw)
        if len(cleaned) < 3:
            raise ValueError("normalized 후 키워드가 3개 미만")
        return cleaned


class QuickSummary(BaseModel):
    """간단 요약 (Role 3: 한국어 3문장 + 핵심 키워드 3~6개)."""

    summary_kr: str = Field(
        ...,
        min_length=20,
        max_length=600,
        description="한국어 2~3문장 요약 (총 600자 이내)",
    )
    key_terms: List[str] = Field(
        ...,
        min_length=2,
        max_length=8,
        description="이 논문의 핵심 용어 2~8개 (영어 또는 한국어)",
    )

    @field_validator("summary_kr")
    @classmethod
    def summary_collapse_whitespace(cls, v: str) -> str:
        return " ".join(v.split())

    @field_validator("key_terms")
    @classmethod
    def normalize_key_terms(cls, v: List[str]) -> List[str]:
        cleaned = []
        seen = set()
        for t in v:
            t = " ".join(t.split()).strip()
            if not t or len(t) > 60:
                continue
            key = t.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(t)
        if len(cleaned) < 2:
            raise ValueError("normalized 후 key_terms 2개 미만")
        return cleaned


# ==============================================================================
# Phase B 추가 — 16개 호출 사이트가 strict_call로 마이그레이션할 때 사용할 스키마
# ==============================================================================


class TagSuggestion(BaseModel):
    """ai.py:suggest_tags용. 논문 1건 → 태그 3~5개."""

    tags: List[str] = Field(..., min_length=1, max_length=10)

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, v: List[str]) -> List[str]:
        out: List[str] = []
        seen: set[str] = set()
        for t in v:
            if not isinstance(t, str):
                continue
            s = t.strip()
            if not s or len(s) > 60:
                continue
            key = s.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(s)
        if not out:
            raise ValueError("유효한 태그가 없음")
        return out


class AnalysisResult(BaseModel):
    """ai.py:analyze_paper(structured)용. 호환을 위해 자유 필드 허용 + 핵심 필드만 강제.

    호출부가 result_text(JSON 문자열)을 그대로 보존하고 parse_json_response를 다시
    돌리는 구조라 strict 검증보다는 "JSON 객체임"만 보장하면 충분하다.
    """

    model_config = {"extra": "allow"}

    summary: Optional[str] = None
    keywords: Optional[List[str]] = None


class ExpandedQuery(BaseModel):
    """search.py:generate_queries_and_terms용."""

    expanded_terms: str = ""
    queries: List[str] = Field(..., min_length=1, max_length=12)
    must_contain_terms: List[str] = Field(default_factory=list)

    @field_validator("queries")
    @classmethod
    def clean_queries(cls, v: List[str]) -> List[str]:
        out = [q.strip() for q in v if isinstance(q, str) and q.strip()]
        if not out:
            raise ValueError("queries 비어있음")
        return out[:12]

    @field_validator("must_contain_terms")
    @classmethod
    def clean_terms(cls, v: List[str]) -> List[str]:
        return [t.strip().lower() for t in v if isinstance(t, str) and t.strip()][:10]


class ScoredPaper(BaseModel):
    """search.py:ai_score_papers의 배치 응답 1건."""

    id: int
    score: float = Field(..., ge=0, le=10)
    reason: str = ""


class ScoredPaperList(BaseModel):
    """list[ScoredPaper] 래퍼 (Ollama format은 객체 루트를 선호)."""

    scores: List[ScoredPaper]


class RelevanceScore(BaseModel):
    """alerts.py:_score_relevance용. 정수 0~10 점수 + 짧은 이유."""

    score: float = Field(..., ge=0, le=10)
    reason: str = ""

