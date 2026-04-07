"""LLM 호출 실패 예외 계층 (PLAN §B.1).

호출부는 LLMError 하위 예외를 잡아 사용자 가시 에러로 변환한다.
strict_call은 절대 폴백 값을 반환하지 않고, 실패 시 항상 LLMError 하위를 raise.
"""
from __future__ import annotations

from typing import Optional


class LLMError(Exception):
    """모든 LLM 실패의 베이스."""

    def __init__(
        self,
        message: str,
        *,
        last_raw: Optional[str] = None,
        last_error: Optional[BaseException] = None,
    ) -> None:
        super().__init__(message)
        self.last_raw = last_raw
        self.last_error = last_error


class LLMTimeoutError(LLMError):
    """타임아웃 (httpx.TimeoutException 등)."""


class LLMSchemaError(LLMError):
    """JSON 파싱 또는 pydantic 검증 실패. 재시도까지 다 써도 검증 통과 못 한 경우."""


class LLMUpstreamError(LLMError):
    """5xx, 연결 실패 등 상위 시스템 문제."""
