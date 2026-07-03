"""Сервис извлечения сущностей и связей через LLM"""
import json
import hashlib
from typing import Any
import httpx
from app.core.config import settings
from app.utils.prompts import ENTITY_EXTRACTION_PROMPT, RELATION_EXTRACTION_PROMPT
from app.utils.synonymus import normalize_entity
from app.db.database import redis_client


class ExtractionService:
    """Извлечение сущностей и связей из текста с кэшированием"""
    
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.use_openai = bool(self.api_key)
        self.model = "gpt-4o-mini"
        self.cache_ttl = 3600
    
    def _get_cache_key(self, text: str, prompt_type: str) -> str:
        text_hash = hashlib.md5(text.encode()).hexdigest()
        return f"extraction:{prompt_type}:{text_hash}"
    
    def _get_cached(self, key: str) -> dict | None:
        try:
            cached = redis_client.get(key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass
        return None
    
    def _set_cached(self, key: str, data: dict):
        try:
            redis_client.setex(key, self.cache_ttl, json.dumps(data))
        except Exception:
            pass
    
    async def extract_entities(self, text: str) -> list[dict[str, Any]]:
        cache_key = self._get_cache_key(text, "entities")
        cached = self._get_cached(cache_key)
        if cached:
            return cached.get("entities", [])
        
        prompt = ENTITY_EXTRACTION_PROMPT.format(text=text[:4000])
        response = await self._call_llm(prompt)
        
        try:
            json_str = self._extract_json(response)
            data = json.loads(json_str)
            entities = data.get("entities", [])
            
            for entity in entities:
                entity["canonical_name"] = normalize_entity(
                    entity.get("canonical_name", entity["name"]),
                    entity.get("type")
                )
            
            self._set_cached(cache_key, {"entities": entities})
            return entities
            
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Ошибка парсинга entities: {e}, response: {response[:200]}")
            return self._fallback_extract_entities(text)
    
    async def extract_relations(self, text: str, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cache_key = self._get_cache_key(text + str(entities), "relations")
        cached = self._get_cached(cache_key)
        if cached:
            return cached.get("relations", [])
        
        entities_list = "\n".join([
            f"- {e['name']} ({e['type']}, каноническое: {e['canonical_name']})"
            for e in entities[:20]
        ])
        
        prompt = RELATION_EXTRACTION_PROMPT.format(text=text[:3000], entities_list=entities_list)
        response = await self._call_llm(prompt)
        
        try:
            json_str = self._extract_json(response)
            data = json.loads(json_str)
            relations = data.get("relations", [])
            self._set_cached(cache_key, {"relations": relations})
            return relations
            
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Ошибка парсинга relations: {e}")
            return self._fallback_extract_relations(text, entities)
    
    async def extract_batch(self, texts: list[str]) -> list[list[dict[str, Any]]]:
        results = []
        for text in texts:
            entities = await self.extract_entities(text)
            results.append(entities)
        return results
    
    def _extract_json(self, text: str) -> str:
        text = text.strip()
        
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        
        text = text.strip()
        
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return text[start:end]
        
        return text
    
    async def _call_llm(self, prompt: str) -> str:
        if self.use_openai:
            return await self._call_openai(prompt)
        else:
            return await self._call_ollama(prompt)
    
    async def _call_openai(self, prompt: str) -> str:
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
                        {"role": "system", "content": "Ты — экспертная система для извлечения структурированных данных. Отвечай ТОЛЬКО валидным JSON."},
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
        import re
        entities = []
        
        chem_pattern = r'\b([A-Z][a-z]?\d*(?:[A-Z][a-z]?\d*)*(?:[-–][A-Z][a-z]?\d*(?:[A-Z][a-z]?\d*)*)?)\b'
        for match in re.finditer(chem_pattern, text):
            entities.append({
                "name": match.group(1),
                "canonical_name": match.group(1),
                "type": "Material",
                "context": text[max(0, match.start()-50):match.end()+50]
            })
        
        process_keywords = ["электроэкстракция", "плавка", "выщелачивание", "обессоливание", "флотация"]
        for keyword in process_keywords:
            for match in re.finditer(rf'\b{keyword}\w*\b', text, re.IGNORECASE):
                entities.append({
                    "name": match.group(0),
                    "canonical_name": keyword,
                    "type": "Process",
                    "context": text[max(0, match.start()-50):match.end()+50]
                })
        
        return entities
    
    def _fallback_extract_relations(self, text: str, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        relations = []
        entity_names = {e["name"] for e in entities}
        
        for e1 in entities:
            for e2 in entities:
                if e1["name"] == e2["name"]:
                    continue
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