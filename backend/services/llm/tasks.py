"""
자율 연구 에이전트의 LLM 작업 단위 (Role 1/2/3).

각 함수는 strict_call을 한 번만 호출하고, 검증된 Pydantic 객체를 반환한다.
실패 시 StrictCallError 전파.
"""
from typing import List, Optional

from .ollama_client import strict_call, DEFAULT_MODEL
from .prompts import (
    KEYWORDS_SYSTEM,
    RELEVANCE_SYSTEM,
    SUMMARY_SYSTEM,
    build_keywords_user,
    build_relevance_user,
    build_summary_user,
)
from .schemas import KeywordList, QuickSummary, RelevanceJudgment


# Role 1: 키워드 생성
async def extract_keywords(
    topic: str,
    exclude: Optional[List[str]] = None,
    *,
    model: str = DEFAULT_MODEL,
) -> KeywordList:
    """주제 → 영어 검색 키워드 3~8개."""
    return await strict_call(
        system=KEYWORDS_SYSTEM,
        user=build_keywords_user(topic, exclude or []),
        schema=KeywordList,
        model=model,
        num_predict=300,  # 키워드 8개까지 여유
    )


# Role 2: 관련도 평가
async def score_relevance(
    topic: str,
    title: str,
    abstract: str,
    *,
    model: str = DEFAULT_MODEL,
) -> RelevanceJudgment:
    """주제 + 논문 (제목+초록) → 0~9 점수 + 한국어 한 문장 이유."""
    return await strict_call(
        system=RELEVANCE_SYSTEM,
        user=build_relevance_user(topic, title, abstract),
        schema=RelevanceJudgment,
        model=model,
        num_predict=200,  # 점수 + 짧은 이유면 충분
    )


# Role 3: 요약
async def summarize(
    title: str,
    abstract: str,
    *,
    model: str = DEFAULT_MODEL,
) -> QuickSummary:
    """제목+초록 → 한국어 2~3문장 요약 + 핵심 용어."""
    return await strict_call(
        system=SUMMARY_SYSTEM,
        user=build_summary_user(title, abstract),
        schema=QuickSummary,
        model=model,
        num_predict=500,  # 요약 + 키워드라 약간 더 길게
    )
