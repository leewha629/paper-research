"""
Strict Ollama client — Gemma 4B 같은 작은 모델이 지침을 따르도록 강제한다.

9가지 방어선:
1. format=json 또는 format=<JSON Schema>  → 디코더 레벨에서 JSON 외 출력 차단
2. temperature 0.1 + top_p 0.9            → 결정성 작업의 흔들림 최소화
3. num_predict 제한                        → 잡설 늘어놓을 여지 차단
4. stop tokens                             → JSON 끝난 뒤 설명 시작 시 즉시 중단
5. 응답 정규화 (마크다운/코드펜스 제거)     → 사후 보정
6. Pydantic 검증                           → 잘못된 출력 거부
7. 자동 재시도 (최대 3회, temp 점진 ↓)     → 일시적 실패 복구
8. keep_alive 30m                          → 모델 메모리 유지 (속도)
9. 실패 시 logging                         → 디버깅/감사

사용:
    from services.llm import strict_call, RelevanceJudgment
    result = await strict_call(
        system="...",
        user="...",
        schema=RelevanceJudgment,
    )
    # → RelevanceJudgment 인스턴스
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal, Optional, Type, TypeVar, Union, overload

import httpx
from pydantic import BaseModel, ValidationError

from .exceptions import (
    LLMError,
    LLMSchemaError,
    LLMTimeoutError,
    LLMUpstreamError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

ExpectMode = Literal["text", "json", "schema"]

# ==============================================================================
# 설정
# ==============================================================================

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "gemma4:e4b"
DEFAULT_KEEP_ALIVE = "30m"
DEFAULT_TIMEOUT = 180.0  # 첫 호출은 모델 로딩으로 길 수 있음
MAX_RETRIES = 3

# 재시도마다 temperature를 더 낮춤 (0.1 → 0.05 → 0.0)
TEMPERATURE_LADDER = [0.1, 0.05, 0.0]

# 출력 길이 기본값 (작업별로 override 가능)
DEFAULT_NUM_PREDICT = 250

# JSON 끝난 뒤 설명을 붙이려고 할 때 차단하는 stop tokens
DEFAULT_STOP_TOKENS = ["\n\n", "```", "Note:", "Explanation:", "주의:", "설명:"]


# ==============================================================================
# 예외
# ==============================================================================

class StrictCallError(LLMSchemaError):
    """레거시 별칭. PLAN B.1의 LLMSchemaError와 동일하게 동작.

    backward compat을 위해 RuntimeError 대신 LLMSchemaError를 상속한다.
    기존 services/llm/tasks.py 등 호출부는 그대로 import할 수 있다.
    """


# ==============================================================================
# 응답 정규화 (방어선 5)
# ==============================================================================

_FENCE_RE = re.compile(r"^```(?:json|JSON)?\s*", re.MULTILINE)
_FENCE_END_RE = re.compile(r"\s*```\s*$", re.MULTILINE)


def clean_json_response(text: str) -> str:
    """모델이 마크다운/잡설을 섞어도 JSON 본체만 추출."""
    if not text:
        return text
    s = text.strip()
    # 마크다운 코드펜스 제거
    s = _FENCE_RE.sub("", s)
    s = _FENCE_END_RE.sub("", s)
    s = s.strip("`").strip()

    # JSON 객체 또는 배열 본체만 자름
    # 우선 객체 시도
    obj_start = s.find("{")
    obj_end = s.rfind("}")
    arr_start = s.find("[")
    arr_end = s.rfind("]")

    if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
        # 객체 + 배열 둘 다 있으면 더 바깥쪽 것 선택
        if arr_start != -1 and arr_end != -1 and (arr_start < obj_start or arr_end > obj_end):
            return s[arr_start : arr_end + 1]
        return s[obj_start : obj_end + 1]
    if arr_start != -1 and arr_end != -1 and arr_end > arr_start:
        return s[arr_start : arr_end + 1]
    return s


# ==============================================================================
# Ollama 호출 (저수준)
# ==============================================================================

async def _ollama_chat(
    *,
    base_url: str,
    model: str,
    system: str,
    user: str,
    format_value,
    temperature: float,
    num_predict: int,
    stop: Optional[list],
    keep_alive: str,
    timeout: float,
) -> str:
    """단일 호출. JSON/스키마 모드 지원. 응답의 message.content 문자열 반환."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "format": format_value,            # 방어선 1
        "keep_alive": keep_alive,          # 방어선 8
        "options": {
            "temperature": temperature,    # 방어선 2
            "top_p": 0.9,
            "num_predict": num_predict,    # 방어선 3
            "stop": stop or [],            # 방어선 4
        },
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(f"{base_url}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data["message"]["content"]


# ==============================================================================
# 핵심: strict_call (Pydantic 검증 + 재시도)
# ==============================================================================

async def strict_call(
    *,
    system: str,
    user: str,
    expect: ExpectMode = "schema",
    schema: Optional[Type[T]] = None,
    images: Optional[list] = None,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    max_retries: int = 2,
    num_predict: int = DEFAULT_NUM_PREDICT,
    stop: Optional[list] = None,
    keep_alive: str = DEFAULT_KEEP_ALIVE,
    timeout_s: float = DEFAULT_TIMEOUT,
    temperature: Optional[float] = None,
    use_schema_format: bool = True,
) -> Union[str, dict, T]:
    """PLAN §B.1 — 모든 LLM 호출의 단일 진입점.

    expect="text"   → str 반환 (정규화 없음, 응답 텍스트 그대로)
    expect="json"   → dict 반환 (json.loads + 코드펜스 제거)
    expect="schema" → schema 인스턴스 반환 (pydantic validate)

    실패 시 반드시 LLMError 하위 예외를 raise. 절대 폴백 값을 반환하지 않는다.
    내부 재시도는 (max_retries+1)회 (PLAN B.1 = 기존 0,1,2 = 총 3회). 마지막 재시도까지
    실패하면 raise.

    images: 향후 multimodal 지원용 placeholder. 현재 ollama_client에서는 무시.
    """
    if expect == "schema" and schema is None:
        raise ValueError("expect='schema'에는 schema= 인자가 필수")

    stop_tokens = stop if stop is not None else (
        DEFAULT_STOP_TOKENS if expect != "text" else []
    )
    total_attempts = max(1, max_retries + 1)

    # 방어선 1: format 결정
    json_schema = None
    if expect == "schema" and use_schema_format and schema is not None:
        try:
            json_schema = schema.model_json_schema()
        except Exception as e:
            logger.warning(f"schema 추출 실패, format='json' 사용: {e}")

    last_raw: Optional[str] = None
    last_error: Optional[BaseException] = None

    for attempt in range(total_attempts):
        # temperature 사다리 (text 모드는 user override가 우선)
        if temperature is not None:
            attempt_temp = temperature
        else:
            attempt_temp = TEMPERATURE_LADDER[min(attempt, len(TEMPERATURE_LADDER) - 1)]
            if expect == "text" and attempt == 0:
                attempt_temp = 0.7  # text 기본은 약간 높게

        # format 모드:
        #   text:   None (format 미지정)
        #   json:   "json"
        #   schema: 1차 schema, 2~3차 "json" fallback
        if expect == "text":
            format_value = None
        elif expect == "json":
            format_value = "json"
        else:  # schema
            if attempt == 0 and json_schema is not None:
                format_value = json_schema
            else:
                format_value = "json"

        # 재시도 시 더 강한 사용자 프롬프트 (json/schema에만)
        actual_user = user
        if attempt > 0 and expect != "text":
            actual_user = (
                user
                + "\n\nIMPORTANT: Previous response was invalid. "
                "Output ONLY a valid JSON object that matches the schema. "
                "No prose, no markdown, no explanation."
            )

        try:
            raw = await _ollama_chat(
                base_url=base_url,
                model=model,
                system=system,
                user=actual_user,
                format_value=format_value,
                temperature=attempt_temp,
                num_predict=num_predict,
                stop=stop_tokens,
                keep_alive=keep_alive,
                timeout=timeout_s,
            )
        except httpx.HTTPStatusError as e:
            logger.warning(
                f"[strict_call] HTTP {e.response.status_code} (시도 {attempt+1}): {e.response.text[:200]}"
            )
            last_error = e
            continue
        except httpx.TimeoutException as e:
            logger.error(f"[strict_call] timeout (시도 {attempt+1}): {e}")
            last_error = e
            if attempt == total_attempts - 1:
                raise LLMTimeoutError(
                    f"strict_call 타임아웃: {timeout_s}s × {total_attempts}회",
                    last_raw=last_raw,
                    last_error=e,
                ) from e
            continue
        except httpx.ConnectError as e:
            logger.error(f"[strict_call] 연결 실패 (시도 {attempt+1}): {e}")
            last_error = e
            if attempt == total_attempts - 1:
                raise LLMUpstreamError(
                    f"strict_call 연결 실패: {base_url}",
                    last_raw=last_raw,
                    last_error=e,
                ) from e
            continue

        last_raw = raw

        # text 모드: 그대로 반환
        if expect == "text":
            return raw

        # json/schema: 정규화 + 파싱
        cleaned = clean_json_response(raw)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(
                f"[strict_call] JSON 파싱 실패 (시도 {attempt+1}): {e} | raw={raw[:200]!r}"
            )
            last_error = e
            continue

        if expect == "json":
            return data

        # schema 검증
        assert schema is not None  # mypy
        try:
            instance = schema.model_validate(data)
            if attempt > 0:
                logger.info(f"[strict_call] 시도 {attempt+1}회만에 성공")
            return instance
        except ValidationError as e:
            logger.warning(
                f"[strict_call] 스키마 검증 실패 (시도 {attempt+1}): {e.errors()[:2]} | data={str(data)[:200]}"
            )
            last_error = e
            continue

    # 모든 재시도 소진 → LLMSchemaError raise (text 모드는 위에서 이미 return)
    raise LLMSchemaError(
        f"strict_call 실패: {total_attempts}회 재시도 모두 검증 통과 못함 "
        f"(expect={expect}, schema={getattr(schema, '__name__', None)})",
        last_raw=last_raw,
        last_error=last_error,
    )
