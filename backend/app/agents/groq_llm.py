import json
from typing import Any
import httpx

from backend.app.core.config import settings


class GroqLLMClient:
    """Client for Groq API (chat only, no embeddings)"""

    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.base_url = "https://api.groq.com/openai/v1"
        self.model = settings.GROQ_MODEL or "llama-3.1-70b-versatile"
        self.available = bool(self.api_key)

        if self.available:
            print(f"✅ Groq клиент подключён: {self.model}")
        else:
            print(f"❌ GROQ_API_KEY не задан")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 4000,
        json_mode: bool = True,
    ) -> str:
        """Синхронный чат с Groq"""
        if not self.available:
            raise RuntimeError("Groq не доступен: нет API ключа")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

        except Exception as e:
            print(f"Ошибка Groq chat: {e}")
            raise

    def chat_completion_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 4000,
    ) -> dict[str, Any]:
        """Чат с парсингом ответа как JSON"""
        try:
            response_text = self.chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=True,
            )
            return self._extract_json(response_text)
        except Exception as e:
            return {"error": str(e), "raw": ""}

    def generate(self, prompt: str, system: str = "", temperature: float = 0.1) -> str:
        """Прямая генерация"""
        return self.chat_completion(
            system_prompt=system,
            user_prompt=prompt,
            temperature=temperature,
        )

    def _extract_json(self, text: str) -> dict[str, Any]:
        """Извлечь JSON из ответа LLM"""
        text = text.strip()

        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        start = text.find("{")
        end = text.rfind("}") + 1

        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        start_arr = text.find("[")
        end_arr = text.rfind("]") + 1

        if start_arr >= 0 and end_arr > start_arr:
            try:
                return {"data": json.loads(text[start_arr:end_arr])}
            except json.JSONDecodeError:
                pass

        return {"error": "parse_failed", "raw": text}


# Синглтон
groq_llm = GroqLLMClient()