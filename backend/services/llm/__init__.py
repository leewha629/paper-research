"""
자율 연구 에이전트용 LLM 호출 모듈.

작은 모델(Gemma 4B)이 지침을 잘 따르도록 9가지 방어선을 적용한 strict 클라이언트 제공.

공개 API:
    from services.llm import strict_call, RelevanceJudgment, KeywordList, QuickSummary
    from services.llm import score_relevance, extract_keywords, summarize
"""
from .schemas import (
    RelevanceJudgment,
    KeywordList,
    QuickSummary,
    TagSuggestion,
    AnalysisResult,
    ExpandedQuery,
    ScoredPaper,
    ScoredPaperList,
    RelevanceScore,
)
from .exceptions import (
    LLMError,
    LLMTimeoutError,
    LLMSchemaError,
    LLMUpstreamError,
)
from .ollama_client import strict_call, StrictCallError
from .router import call_llm, get_active_backend
from .tasks import score_relevance, extract_keywords, summarize

__all__ = [
    "strict_call",
    "call_llm",
    "get_active_backend",
    "StrictCallError",
    "LLMError",
    "LLMTimeoutError",
    "LLMSchemaError",
    "LLMUpstreamError",
    "RelevanceJudgment",
    "KeywordList",
    "QuickSummary",
    "TagSuggestion",
    "AnalysisResult",
    "ExpandedQuery",
    "ScoredPaper",
    "ScoredPaperList",
    "RelevanceScore",
    "score_relevance",
    "extract_keywords",
    "summarize",
]
