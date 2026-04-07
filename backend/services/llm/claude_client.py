"""Anthropic Claude용 strict_call (PLAN §B.2).

ollama_client.strict_call과 동일한 시그니처/의미. 차이점:
- 디코더 레벨 JSON 강제가 없으므로 프롬프트로만 강제
- pydantic 검증은 동일
- 재시도/예외 매핑 동일
"""
from __future__ import annotations

import base64
import json
import logging
from typing import Any, Literal, Optional, Type, TypeVar, Union

from pydantic import BaseModel, ValidationError

from .exceptions import (
    LLMError,
    LLMSchemaError,
    LLMTimeoutError,
    LLMUpstreamError,
)
from .ollama_client import clean_json_response

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
ExpectMode = Literal["text", "json", "schema"]

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_TIMEOUT = 120.0


async def strict_call(
    *,
    api_key: str,
    system: str,
    user: str,
    expect: ExpectMode = "schema",
    schema: Optional[Type[T]] = None,
    images: Optional[list] = None,
    model: str = DEFAULT_MODEL,
    max_retries: int = 2,
    timeout_s: float = DEFAULT_TIMEOUT,
    temperature: Optional[float] = None,
    max_tokens: int = 4096,
) -> Union[str, dict, T]:
    """Claude를 통한 strict_call. ollama 버전과 동일 의미."""
    if expect == "schema" and schema is None:
        raise ValueError("expect='schema'에는 schema= 인자가 필수")

    try:
        import anthropic
    except ImportError as e:
        raise LLMUpstreamError("anthropic 패키지 미설치") from e

    client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout_s)

    # JSON/schema 모드면 system 프롬프트에 강제 지침 추가
    actual_system = system
    if expect != "text":
        actual_system = (
            system
            + "\n\nIMPORTANT: Respond with ONLY a valid JSON object. "
            "No prose, no markdown code fences, no explanation."
        )

    content: list[dict[str, Any]] = []
    if images:
        for img in images:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": base64.b64encode(img).decode(),
                    },
                }
            )
    content.append({"type": "text", "text": user})

    total_attempts = max(1, max_retries + 1)
    last_raw: Optional[str] = None
    last_error: Optional[BaseException] = None

    for attempt in range(total_attempts):
        attempt_temp = temperature if temperature is not None else (
            0.1 if expect != "text" else 0.7
        )
        try:
            resp = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=attempt_temp,
                system=actual_system,
                messages=[{"role": "user", "content": content}],
            )
        except anthropic.APITimeoutError as e:
            last_error = e
            if attempt == total_attempts - 1:
                raise LLMTimeoutError(
                    f"Claude 타임아웃: {timeout_s}s × {total_attempts}회",
                    last_raw=last_raw,
                    last_error=e,
                ) from e
            continue
        except anthropic.APIConnectionError as e:
            last_error = e
            if attempt == total_attempts - 1:
                raise LLMUpstreamError(
                    "Claude 연결 실패",
                    last_raw=last_raw,
                    last_error=e,
                ) from e
            continue
        except anthropic.APIStatusError as e:
            last_error = e
            logger.warning(f"[claude.strict_call] {e.status_code}: {str(e)[:200]}")
            if attempt == total_attempts - 1:
                raise LLMUpstreamError(
                    f"Claude HTTP {e.status_code}",
                    last_raw=last_raw,
                    last_error=e,
                ) from e
            continue

        raw = resp.content[0].text if resp.content else ""
        last_raw = raw

        if expect == "text":
            return raw

        cleaned = clean_json_response(raw)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(
                f"[claude.strict_call] JSON 파싱 실패 (시도 {attempt+1}): raw={raw[:200]!r}"
            )
            last_error = e
            continue

        if expect == "json":
            return data

        assert schema is not None
        try:
            return schema.model_validate(data)
        except ValidationError as e:
            logger.warning(
                f"[claude.strict_call] 스키마 검증 실패 (시도 {attempt+1}): {e.errors()[:2]}"
            )
            last_error = e
            continue

    raise LLMSchemaError(
        f"claude.strict_call 실패: {total_attempts}회 재시도 모두 검증 통과 못함 "
        f"(expect={expect}, schema={getattr(schema, '__name__', None)})",
        last_raw=last_raw,
        last_error=last_error,
    )
