import base64
import json
import re
import httpx
import anthropic
from typing import Optional, Tuple


class AIClient:
    def __init__(self, db):
        self.db = db

    def _get_setting(self, key: str) -> str:
        from models import AppSetting
        s = self.db.query(AppSetting).filter(AppSetting.key == key).first()
        return s.value if s and s.value else ""

    def _get_prompt(self, name: str) -> Optional[str]:
        """DB에 저장된 커스텀 프롬프트 조회"""
        from models import PromptTemplate
        pt = self.db.query(PromptTemplate).filter(PromptTemplate.name == name).first()
        return pt.system_prompt if pt else None

    async def complete(
        self,
        system: str,
        user: str,
        images: list = None,
        max_retries: int = 2,
        expect_json: bool = False,
    ) -> Tuple[str, str, str]:
        """**[DEPRECATED — Phase B 어댑터]**

        새 코드는 `services.llm.router.call_llm`을 직접 사용한다. 이 함수는
        Phase A 회귀 테스트(#1~#4)가 잠그는 retry/JSON 폴백 시맨틱을 보존하기
        위해 그대로 남는다. Phase C에서 fail-loud 마이그레이션과 함께 제거 예정.

        Returns (result_text, backend, model_name). JSON 파싱 실패 시 재시도.
        폴백 분기(마지막 시도도 invalid면 raw 텍스트 그대로 반환)는 PLAN §B.2
        지침에 따라 그대로 유지 — Phase C가 LLMSchemaError raise로 교체.
        """
        backend = self._get_setting("ai_backend") or "claude"

        for attempt in range(max_retries + 1):
            try:
                if backend == "claude":
                    result, be, model = await self._claude(system, user, images)
                else:
                    result, be, model = await self._ollama(system, user, expect_json=expect_json)

                if expect_json:
                    # JSON 파싱 시도
                    clean = re.sub(r"```[a-z]*\n?", "", result).strip().rstrip("`")
                    json.loads(clean)  # 파싱 테스트

                return result, be, model

            except json.JSONDecodeError:
                if attempt < max_retries:
                    # JSON 파싱 실패 시 재시도 프롬프트 보강
                    user = user + "\n\nIMPORTANT: Your previous response was not valid JSON. Return ONLY valid JSON with no markdown formatting, no explanation, no text before or after the JSON."
                    continue
                # 마지막 시도도 실패하면 원본 반환
                return result, be, model

            except Exception:
                if attempt < max_retries and expect_json:
                    continue
                raise

    async def _claude(self, system: str, user: str, images=None) -> Tuple[str, str, str]:
        api_key = self._get_setting("claude_api_key")
        if not api_key:
            raise ValueError("Claude API 키가 설정되지 않았습니다.")
        client = anthropic.AsyncAnthropic(api_key=api_key)
        model = "claude-sonnet-4-20250514"

        content = []
        if images:
            for img in images:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": base64.b64encode(img).decode(),
                    },
                })
        content.append({"type": "text", "text": user})

        resp = await client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": content}],
        )
        return resp.content[0].text, "claude", model

    async def _ollama(self, system: str, user: str, expect_json: bool = False) -> Tuple[str, str, str]:
        base_url = self._get_setting("ollama_base_url") or "http://localhost:11434"
        model = self._get_setting("ollama_model") or "gemma4:e4b"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "keep_alive": "30m",  # 마지막 호출 후 30분 동안 RAM/VRAM 상주
            "options": {
                # JSON 모드일 때는 결정성 ↑
                "temperature": 0.1 if expect_json else 0.7,
                "top_p": 0.9,
            },
        }
        if expect_json:
            # 디코더 레벨 JSON 강제 (Gemma 같은 작은 모델의 잡설 차단)
            payload["format"] = "json"
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.post(
                    f"{base_url}/api/chat",
                    json=payload,
                )
                resp.raise_for_status()
            return resp.json()["message"]["content"], "ollama", model
        except httpx.ConnectError:
            raise ConnectionError(f"Ollama 서버({base_url})에 연결할 수 없습니다. Ollama가 실행 중인지 확인하세요.")
        except httpx.TimeoutException:
            raise TimeoutError(f"Ollama 응답 시간 초과 ({model}). 모델 로딩 중일 수 있습니다.")

    async def test_connection(self) -> dict:
        backend = self._get_setting("ai_backend") or "claude"
        try:
            text, _, model = await self.complete(
                "You are a helpful assistant.", "Reply with just: OK"
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


def parse_json_response(text: str) -> dict:
    """AI 응답에서 JSON 추출 (마크다운 코드블록 제거)"""
    clean = re.sub(r"```[a-z]*\n?", "", text).strip().rstrip("`")
    # JSON 배열 또는 객체 찾기
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = clean.find(start_char)
        end = clean.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(clean[start:end + 1])
            except json.JSONDecodeError:
                continue
    return json.loads(clean)
