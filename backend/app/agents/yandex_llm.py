"""Клинет для Yandex rest api"""
import json
from typing import Any
from openai import OpenAI
from ..core.config import settings


class YandexLLMClient:
    """
    Клиент для Yandex GPT API.
    Использует OpenAI-совместимый интерфейс.
    """
    
    def __init__(self):
        self.api_key = settings.YANDEX_API_KEY
        self.folder_id = settings.YANDEX_FOLDER_ID
        self.base_url = settings.YANDEX_BASE_URL
        self.model = settings.YANDEX_MODEL
        
        if self.api_key and self.folder_id:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url, 
                timeout=60.0,
                max_retries=2,
            )
            print(f"Yandex LLM клиент инициализирован: {self.model}")
        else:
            print("Yandex API ключ не настроен — будет использоваться fallback")
            self.client = None
    
    def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> str:
        """
        вызов chat completion.
        Возвращает текст ответа.
        """
        if not self.client:
            return self._fallback_response(system_prompt, user_prompt)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        if json_mode:
            messages[1]["content"] += "\n\nОтвет дожен быть только в формате JSON"
        
        try:
            response = self.client.chat.completions.create(
                model=f"gpt://{self.folder_id}/{self.model}",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens, 
                extra_body={
                    "folder_id": self.folder_id
                }
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"Ошибка Yandex API: {e}")
            if hasattr(e, 'response'):
                print(f"   Статус: {e.response.status_code}")
                print(f"   Тело: {e.response.text}")
            raise
    
    def chat_completion_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> dict[str, Any]:
        """
        Вызывает API и парсит ответ как JSON.
        Если парсинг не удался — возвращает {"error": "parse_failed", "raw": "..."}
        """
        try:
            response_text = self.chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens, 
                json_mode=True
            )
            
            # Извлекаем JSON из ответа
            return self._extract_json(response_text)
            
        except Exception as e:
            return {"error": str(e), "raw": ""}
    
    def _extract_json(self, text: str) -> dict[str, Any]:
        """Извлекает JSON из ответа LLM"""
        text = text.strip()
        
        # Убираем markdown code blocks
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        
        if text.endswith("```"):
            text = text[:-3]
        
        text = text.strip()
        
        # Находим JSON объект
        start = text.find("{")
        end = text.rfind("}") + 1
        
        if start >= 0 and end > start:
            json_str = text[start:end]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
        
        # Пробуем найти JSON массив
        start_arr = text.find("[")
        end_arr = text.rfind("]") + 1
        
        if start_arr >= 0 and end_arr > start_arr:
            try:
                return {"data": json.loads(text[start_arr:end_arr])}
            except json.JSONDecodeError:
                pass
        
        # Не удалось распарсить — возвращаем как есть
        return {"error": "parse_failed", "raw": text[:1000]}
    
    def embeddings(self, texts: list) -> list:
        """
        Получить эмбеддинги через Yandex.
        """
        if not self.client:
            return []
        try:
            response = self.client.embeddings.create(
                model="text-embedding",  
                input=texts, 
                extra_body={
                    "folder_id": self.folder_id
                }
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            print(f"Ошибка получения эмбеддингов: {e}")
            raise
    
    def embeddings_batch(self, texts: list[str], batch_size: int = 10) -> list[list[float]]:
        """
        Получение эмбеддингов батчами (если API имеет ограничение).
        """
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = self.embeddings(batch)
            all_embeddings.extend(batch_embeddings)
        
        return all_embeddings
    
    def _fallback_response(self, system_prompt: str, user_prompt: str) -> str:
        """
        Fallback, если API недоступен.
        """
        print("⚠️  Используется fallback (API недоступен)")
        return f"""{{"error": "api_not_available", "message": "Yandex API не настроен или недоступен", "system": "{system_prompt[:50]}...", "user": "{user_prompt}"}}"""


yandex_llm = YandexLLMClient()