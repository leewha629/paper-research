"""Backend 분기 라우터 (PLAN §B.2).

DB의 AppSetting(`ai_backend`, `ollama_*`, `claude_api_key`)을 읽어
ollama_client 또는 claude_client의 strict_call로 위임한다.

호출부는 `call_llm(db, system=..., user=..., expect=..., schema=...)` 한 함수만
알면 된다. backend/model 정보가 필요한 호출부(ai.py의 AIAnalysisResult 등)를 위해
3-튜플 `(value, backend, model)`을 반환한다.
"""
from __future__ import annotations

import json
import re
from typing import Any, Literal, Optional, Type, TypeVar, Union

from pydantic import BaseModel

from . import claude_client as claude
from . import ollama_client as ollama
from .exceptions import LLMUpstreamError

T = TypeVar("T", bound=BaseModel)
ExpectMode = Literal["text", "json", "schema"]


def get_active_backend(db) -> tuple[str, str]:
    """현재 설정된 (backend, model) 반환. DB 미시드면 ollama/기본 모델."""
    from models import AppSetting

    def _get(key: str, default: str = "") -> str:
        s = db.query(AppSetting).filter(AppSetting.key == key).first()
        return s.value if s and s.value else default

    backend = _get("ai_backend", "claude") or "claude"
    if backend == "claude":
        model = claude.DEFAULT_MODEL
    else:
        model = _get("ollama_model", ollama.DEFAULT_MODEL) or ollama.DEFAULT_MODEL
    return backend, model


async def call_llm(
    db,
    *,
    system: str,
    user: str,
    expect: ExpectMode = "schema",
    schema: Optional[Type[T]] = None,
    images: Optional[list] = None,
    max_retries: int = 2,
    timeout_s: float = 120.0,
    temperature: Optional[float] = None,
    num_predict: int = 1024,
) -> tuple[Union[str, dict, T], str, str]:
    """라우터: settings 기반 ollama/claude 분기 후 strict_call.

    반환: (값, backend, model_name)
        - expect="text"  → (str, backend, model)
        - expect="json"  → (dict, backend, model)
        - expect="schema"→ (schema 인스턴스, backend, model)

    실패 시 LLMError 하위 raise (절대 폴백 반환 없음). 호출부에서 try/except 처리.
    """
    from models import AppSetting

    def _get(key: str, default: str = "") -> str:
        s = db.query(AppSetting).filter(AppSetting.key == key).first()
        return s.value if s and s.value else default

    backend = _get("ai_backend", "claude") or "claude"

    if backend == "claude":
        api_key = _get("claude_api_key")
        if not api_key:
            raise LLMUpstreamError("Claude API 키가 설정되지 않았습니다.")
        model = claude.DEFAULT_MODEL
        value = await claude.strict_call(
            api_key=api_key,
            system=system,
            user=user,
            expect=expect,
            schema=schema,
            images=images,
            model=model,
            max_retries=max_retries,
            timeout_s=timeout_s,
            temperature=temperature,
        )
        return value, "claude", model

    # ollama
    base_url = _get("ollama_base_url", ollama.DEFAULT_BASE_URL) or ollama.DEFAULT_BASE_URL
    model = _get("ollama_model", ollama.DEFAULT_MODEL) or ollama.DEFAULT_MODEL
    value = await ollama.strict_call(
        system=system,
        user=user,
        expect=expect,
        schema=schema,
        images=images,
        base_url=base_url,
        model=model,
        max_retries=max_retries,
        num_predict=num_predict,
        timeout_s=timeout_s,
        temperature=temperature,
    )
    return value, "ollama", model


def parse_json_response(text: str) -> dict:
    """AI 응답에서 JSON 추출 (마크다운 코드블록 제거)."""
    clean = re.sub(r"```[a-z]*\n?", "", text).strip().rstrip("`")
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = clean.find(start_char)
        end = clean.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(clean[start : end + 1])
            except json.JSONDecodeError:
                continue
    return json.loads(clean)


async def test_connection(db) -> dict:
    """AI 백엔드 연결 테스트."""
    backend, model = get_active_backend(db)
    try:
        text, _, model = await call_llm(
            db,
            system="You are a helpful assistant.",
            user="Reply with just: OK",
            expect="text",
        )
        return {
            "success": True,
            "backend": backend,
            "model": model,
            "message": f"연결 성공 ({model})",
        }
    except Exception as e:
        return {
            "success": False,
            "backend": backend,
            "model": "",
            "message": str(e),
        }
