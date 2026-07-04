"""Сервис извлечения сущностей и связей через LLM"""
import json
from typing import Any

from ...utils.prompts import ENTITY_EXTRACTION_PROMPT, RELATION_EXTRACTION_PROMPT
from ...utils.synonymus import normalize_entity
from ...agents.yandex_llm import yandex_llm


class ExtractionService:
    """Извлечение сущностей и связей из текста"""
    
    def __init__(self):
        self.llm = yandex_llm
        self.system_prompt = "Ты — экспертная система для извлечения структурированных данных из горно-металлургических текстов. Отвечай ТОЛЬКО валидным JSON без пояснений."
    
    def extract_entities(self, text: str) -> list[dict[str, Any]]:
        prompt = ENTITY_EXTRACTION_PROMPT.format(text=text[:4000])
        
        try:
            response = self.llm.chat_completion_json(
                system_prompt=self.system_prompt, 
                user_prompt=prompt,
                temperature=0.1,
                max_tokens=2000
            )
           
            entities = response.get("entities", [])
            
            for entity in entities:
                entity["canonical_name"] = normalize_entity(
                    entity.get("canonical_name", entity["name"]),
                    entity.get("type")
                )

            return entities
            
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Ошибка парсинга entities: {e}, response: {response[:200]}")
            return self._fallback_extract_entities(text)
    
    def extract_relations(self, text: str, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        entities_list = "\n".join([
            f"- {e['name']} ({e['type']}, каноническое: {e['canonical_name']})"
            for e in entities[:20]
        ])
        
        prompt = RELATION_EXTRACTION_PROMPT.format(text=text[:3000], entities_list=entities_list)
        
        try:
            response = self.llm.chat_completion_json(
                system_prompt=self.system_prompt,
                user_prompt=prompt, 
                temperature=0.1,
                max_tokens=2000,
            )
            relations = response.get("relations", [])
            return relations
            
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Ошибка парсинга relations: {e}")
            return self._fallback_extract_relations(text, entities)
    
    def extract_batch(self, texts: list[str]) -> list[list[dict[str, Any]]]:
        results = []
        for text in texts:
            entities = self.extract_entities(text)
            results.append(entities)
        return results
    
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