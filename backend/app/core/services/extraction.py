import json
import httpx

from typing import Any

from app.core.config import settings
from app.utils.prompts import ENTITY_EXTRACTION_PROMPT, RELATION_EXTRACTION_PROMPT
from app.utils.synonymus import normalize_entity


class ExtractionService:
    """Извлечение сущностей и связей из текста"""
    
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.use_openai = bool(self.api_key)
        self.model = "-"
    
    async def extract_entities(self, text: str) -> list[dict[str, Any]]:
        """Извлечь сущности из текста"""
        prompt = ENTITY_EXTRACTION_PROMPT.format(text=text)
        
        response = await self._call_llm(prompt)
        
        try:
            data = json.loads(response)
            entities = data.get("entities", [])
            
            # Нормализация
            for entity in entities:
                entity["canonical_name"] = normalize_entity(
                    entity.get("canonical_name", entity["name"]),
                    entity.get("type")
                )
            
            return entities
        except json.JSONDecodeError:
            # Fallback: парсим вручную
            return self._fallback_extract_entities(text)
    
    async def extract_relations(self, text: str, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Извлечь связи между сущностями"""
        entities_list = "\\n".join([
            f"- {e['name']} ({e['type']}, каноническое: {e['canonical_name']})"
            for e in entities
        ])
        
        prompt = RELATION_EXTRACTION_PROMPT.format(text=text, entities_list=entities_list)
        
        response = await self._call_llm(prompt)
        
        try:
            data = json.loads(response)
            return data.get("relations", [])
        except json.JSONDecodeError:
            return self._fallback_extract_relations(text, entities)
    
    async def _call_llm(self, prompt: str) -> str:
        """Вызвать LLM API"""
        if self.use_openai:
            return await self._call_openai(prompt)
        else:
            # Fallback: локальная модель через Ollama
            return await self._call_ollama(prompt)
    
    async def _call_openai(self, prompt: str) -> str:
        """Вызвать OpenAI API"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "Ты — экспертная система для извлечения структурированных данных из горно-металлургических текстов. Отвечай ТОЛЬКО валидным JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 2000
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    
    async def _call_ollama(self, prompt: str) -> str:
        """Вызвать локальную модель через Ollama"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "qwen2.5:7b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1}
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["response"]
    
    def _fallback_extract_entities(self, text: str) -> list[dict[str, Any]]:
        """Резервный метод извлечения сущностей (правила)"""
        import re
        entities = []
        
        chem_pattern = r'\\b([A-Z][a-z]?\\d*(?:[A-Z][a-z]?\\d*)*(?:[-–][A-Z][a-z]?\\d*(?:[A-Z][a-z]?\\d*)*)?)\\b'
        for match in re.finditer(chem_pattern, text):
            entities.append({
                "name": match.group(1),
                "canonical_name": match.group(1),
                "type": "Material",
                "context": text[max(0, match.start()-50):match.end()+50]
            })
        
        # Процессы: ключевые слова
        process_keywords = ["электроэкстракция", "плавка", "выщелачивание", "обессоливание", "флотация"]
        for keyword in process_keywords:
            for match in re.finditer(rf'\\b{keyword}\\w*\\b', text, re.IGNORECASE):
                entities.append({
                    "name": match.group(0),
                    "canonical_name": keyword,
                    "type": "Process",
                    "context": text[max(0, match.start()-50):match.end()+50]
                })
        
        return entities
    
    def _fallback_extract_relations(self, text: str, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Резервный метод извлечения связей"""
        relations = []
        entity_names = {e["name"] for e in entities}
        
        # Простые паттерны: "X применяется для Y", "X использует Y"
        for e1 in entities:
            for e2 in entities:
                if e1["name"] == e2["name"]:
                    continue
                # Проверяем близость в тексте
                idx1 = text.find(e1["name"])
                idx2 = text.find(e2["name"])
                if idx1 >= 0 and idx2 >= 0 and abs(idx1 - idx2) < 200:
                    relations.append({
                        "source": e1["name"],
                        "target": e2["name"],
                        "relation_type": "RELATED_TO",
                        "context": text[min(idx1, idx2):max(idx1, idx2)+100],
                        "confidence": 0.5
                    })
        
        return relations

extraction_service = ExtractionService()