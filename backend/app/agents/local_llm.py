import httpx
import json

from typing import Any

from ..core.config import settings


class LocalLLMClient:
    """Client for local models"""

    def __init__(self, model_name: str = "local-llm"):
        self.embed_url = settings.OLLAMA_EMBED_URL
        self.chat_url = settings.OLLAMA_CHAT_URL
        self.chat_model = settings.OLLAMA_CHAT_MODEL
        self.embed_model = settings.OLLAMA_EMBED_MODEL

        self.available = self._check_connection()
        
        if self.available:
            print(f"✅ Local LLM клиент подключён: {self.chat_url}, {self.embed_url}")
            print(f"   Chat model: {self.chat_model}")
            print(f"   Embed model: {self.embed_model}")
        else:
            print(f"❌ Ollama не доступна по {self.embed_url}, {self.chat_url}")
            print("   Запустите: ollama serve")
    
    def _check_connection(self) -> bool:
        """Проверить доступность Ollama"""
        try:
            response1 = httpx.get(f"{self.embed_url}/api/tags", timeout=5.0)
            response2 = httpx.get(f"{self.chat_url}/api/tags", timeout=5.0)
            return response1.status_code == 200 and response2.status_code == 200
        except Exception:
            return False
    
    # def _ensure_model(self, model: str) -> bool:
    #     """Проверить, что модель загружена, иначе попытаться скачать"""
    #     try:
    #         response = httpx.get(f"{self.base_url}/api/tags", timeout=10.0)
    #         data = response.json()
    #         models = [m["name"] for m in data.get("models", [])]
            
    #         if model in models:
    #             return True
            
    #         print(f"⬇️ Модель {model} не найдена. Скачивание...")
    #         # Pull model
    #         pull_response = httpx.post(
    #             f"{self.base_url}/api/pull",
    #             json={"name": model},
    #             timeout=300.0
    #         )
    #         return pull_response.status_code == 200
            
    #     except Exception as e:
    #         print(f"Ошибка проверки модели: {e}")
    #         return False
    
    def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        json_mode: bool = True
    ) -> str:
        """
        Синхронный чат с локальной моделью.
        """
        if not self.available:
            raise RuntimeError("Ollama не доступна")
        
        # if not self._ensure_model(self.chat_model):
        #     raise RuntimeError(f"Модель {self.chat_model} недоступна")
        
        try:
            response = httpx.post(
                f"{self.chat_url}/api/chat",
                json={
                    "model": self.chat_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                },
                timeout=120.0
            )
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]
            
        except Exception as e:
            print(f"Ошибка chat: {e}")
            raise
    
    def chat_completion_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> dict[str, Any]:
        """
        Чат с парсингом ответа как JSON.
        """
        try:
            response_text = self.chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return self._extract_json(response_text)
        except Exception as e:
            return {"error": str(e), "raw": ""}
    
    def embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Получить эмбеддинги через локальную модель.
        """
        if not self.available:
            raise RuntimeError("Ollama не доступна")
        
        # if not self._ensure_model(self.embed_model):
        #     raise RuntimeError(f"Модель {self.embed_model} недоступна")
        
        embeddings = []
        
        for text in texts:
            try:
                response = httpx.post(
                    f"{self.embed_url}/api/embeddings",
                    json={
                        "model": self.embed_model,
                        "prompt": text
                    },
                    timeout=60.0
                )
                response.raise_for_status()
                data = response.json()
                embeddings.append(data["embedding"])
                
            except Exception as e:
                print(f"Ошибка embedding для текста '{text[:50]}...': {e}")
                embeddings.append([0.0] * 768)  # nomic-embed-text = 768
        
        return embeddings
    
    def embed_single(self, text: str) -> list[float]:
        """Эмбеддинг для одного текста"""
        results = self.embeddings([text])
        return results[0] if results else []
    
    def generate(self, prompt: str, system: str = "", temperature: float = 0.1) -> str:
        """
        Прямая генерация через /api/generate (для простых задач).
        """
        if not self.available:
            raise RuntimeError("Ollama не доступна")
        
        try:
            response = httpx.post(
                f"{self.chat_url}/api/generate",
                json={
                    "model": self.chat_model,
                    "prompt": prompt,
                    "system": system,
                    "stream": False,
                    "options": {
                        "temperature": temperature
                    }
                },
                timeout=120.0
            )
            response.raise_for_status()
            return response.json()["response"]
            
        except Exception as e:
            print(f"Ошибка generate: {e}")
            raise
    
    # def list_models(self) -> list[str]:
    #     """Список доступных моделей"""
    #     try:
    #         response = httpx.get(f"{self.base_url}/api/tags", timeout=10.0)
    #         data = response.json()
    #         return [m["name"] for m in data.get("models", [])]
    #     except Exception:
    #         return []
    
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
local_llm = LocalLLMClient()