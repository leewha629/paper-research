import base64
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

    async def complete(
        self,
        system: str,
        user: str,
        images: list = None,
    ) -> Tuple[str, str, str]:
        """Returns (result_text, backend, model_name)"""
        backend = self._get_setting("ai_backend") or "claude"
        if backend == "claude":
            return await self._claude(system, user, images)
        else:
            return await self._ollama(system, user)

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

    async def _ollama(self, system: str, user: str) -> Tuple[str, str, str]:
        base_url = self._get_setting("ollama_base_url") or "http://localhost:11434"
        model = self._get_setting("ollama_model") or "qwen2.5:7b"
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                },
            )
            resp.raise_for_status()
        return resp.json()["message"]["content"], "ollama", model

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
