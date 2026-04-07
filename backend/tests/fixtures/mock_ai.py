"""AIClient mock 헬퍼.

PLAN §A.1 — `AIClient.complete`를 monkeypatch하는 헬퍼 (성공/타임아웃/JSON깨짐 3가지 모드).

이 헬퍼는 **monkeypatch로만** 동작한다 → 실제 ollama/claude 네트워크를 절대
호출하지 않는다 (PLAN §A.3, §A.4 네트워크 차단 검증 요구사항).
"""
from __future__ import annotations

from typing import Any, Optional


class MockAIBehavior:
    """`AIClient.complete` 호출을 가로채 사전 정의된 응답을 반환한다.

    사용 예:
        mock_ai.queue_text("8.5")            # 1회 텍스트 응답
        mock_ai.queue_error(TimeoutError())  # 1회 예외
        mock_ai.set_default_text("OK")       # 큐 소진 후 기본 응답

    응답 큐가 비어 있고 default도 없으면 RuntimeError를 던진다 → 테스트가
    의도하지 않은 호출을 잡아낸다.
    """

    def __init__(self) -> None:
        self._queue: list[tuple[str, Any]] = []
        self._default: Optional[tuple[str, Any]] = None
        self.calls: list[dict] = []

    # ─── 응답 등록 ───────────────────────────────────────────────────────
    def queue_text(self, text: str) -> None:
        self._queue.append(("text", text))

    def queue_error(self, exc: BaseException) -> None:
        self._queue.append(("error", exc))

    def set_default_text(self, text: str) -> None:
        self._default = ("text", text)

    def set_default_error(self, exc: BaseException) -> None:
        self._default = ("error", exc)

    # ─── 호출 진입점 ─────────────────────────────────────────────────────
    async def __call__(
        self,
        system: str,
        user: str,
        images: Optional[list] = None,
        max_retries: int = 2,
        expect_json: bool = False,
    ) -> tuple[str, str, str]:
        self.calls.append(
            {
                "system": system,
                "user": user,
                "images": images,
                "max_retries": max_retries,
                "expect_json": expect_json,
            }
        )
        if self._queue:
            kind, value = self._queue.pop(0)
        elif self._default is not None:
            kind, value = self._default
        else:
            raise RuntimeError(
                "mock_ai: 응답 큐가 비어 있고 default도 없습니다. "
                "테스트가 예상보다 많은 AI 호출을 했을 가능성이 있습니다."
            )

        if kind == "error":
            raise value
        return value, "ollama", "mock-model"


def install_mock_ai(monkeypatch) -> MockAIBehavior:
    """`AIClient.complete` + `services.llm.router.call_llm` 둘 다 MockAIBehavior로 교체.

    Phase B 마이그레이션 후 일부 호출 사이트는 `call_llm`을 거치지만, Phase A
    테스트들은 여전히 `mock_ai`로 동작을 잠그고 있어야 한다 → 두 진입점 모두
    같은 큐를 보도록 같이 패치.

    monkeypatch 스코프가 끝나면 자동으로 원복된다 → 테스트 간 누수 없음.
    """
    mock = MockAIBehavior()

    from ai_client import AIClient

    async def patched_complete(
        self,
        system: str,
        user: str,
        images=None,
        max_retries: int = 2,
        expect_json: bool = False,
    ):
        return await mock(
            system,
            user,
            images=images,
            max_retries=max_retries,
            expect_json=expect_json,
        )

    monkeypatch.setattr(AIClient, "complete", patched_complete)

    # Phase B: services.llm.router.call_llm도 같은 큐를 보도록 패치.
    # 동작: error 항목이면 raise, text 항목이면 expect 모드에 따라 변환:
    #   expect="text"   → (text, "ollama", "mock-model")
    #   expect="json"   → (json.loads(text), "ollama", "mock-model")
    #   expect="schema" → (schema.model_validate(json.loads(text)), ...)
    import json as _json

    async def patched_call_llm(
        db,
        *,
        system: str,
        user: str,
        expect: str = "schema",
        schema=None,
        images=None,
        max_retries: int = 2,
        timeout_s: float = 120.0,
        temperature=None,
        num_predict: int = 1024,
    ):
        # 큐 소비 (mock.__call__과 동일 로직)
        mock.calls.append(
            {
                "system": system,
                "user": user,
                "images": images,
                "max_retries": max_retries,
                "expect_json": expect != "text",
                "expect": expect,
                "schema": getattr(schema, "__name__", None),
            }
        )
        if mock._queue:
            kind, value = mock._queue.pop(0)
        elif mock._default is not None:
            kind, value = mock._default
        else:
            raise RuntimeError(
                "mock_ai(call_llm): 응답 큐가 비어 있고 default도 없습니다."
            )

        if kind == "error":
            raise value

        text = value
        if expect == "text":
            return text, "ollama", "mock-model"

        # json/schema는 실제 dict로 변환
        try:
            data = _json.loads(text)
        except Exception as e:
            from services.llm.exceptions import LLMSchemaError

            raise LLMSchemaError(
                f"mock_ai: queue_text가 유효한 JSON이 아님 (expect={expect}): {text[:80]}",
                last_raw=text,
                last_error=e,
            )
        if expect == "json":
            return data, "ollama", "mock-model"
        # schema
        if schema is None:
            raise ValueError("mock_ai: expect='schema'인데 schema 인자 없음")
        return schema.model_validate(data), "ollama", "mock-model"

    import services.llm.router as _router

    monkeypatch.setattr(_router, "call_llm", patched_call_llm)

    return mock


def install_mock_ollama(monkeypatch, responses: list[Any]) -> dict:
    """`AIClient._ollama` (저수준)를 교체한다.

    `complete` 자체의 retry/JSON 검증 로직을 테스트할 때 사용 — 즉
    Phase A 테스트 #2, #3 (`test_ai_client_contract`).

    responses 항목:
        - 문자열 → 그 텍스트를 반환
        - 예외 인스턴스 → raise

    반환되는 dict는 호출 횟수 추적용 (`state["calls"]`).
    """
    state = {"calls": 0, "responses": list(responses)}

    from ai_client import AIClient

    async def patched_ollama(self, system: str, user: str, expect_json: bool = False):
        idx = state["calls"]
        state["calls"] += 1
        if idx >= len(state["responses"]):
            raise RuntimeError(
                f"mock_ollama: {idx + 1}번째 호출이지만 응답이 {len(state['responses'])}개뿐"
            )
        item = state["responses"][idx]
        if isinstance(item, BaseException):
            raise item
        return item, "ollama", "mock-model"

    monkeypatch.setattr(AIClient, "_ollama", patched_ollama)
    return state
