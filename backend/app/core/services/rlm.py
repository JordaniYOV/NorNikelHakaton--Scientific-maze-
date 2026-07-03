"""Recursive Language Model — рекурсивная система мышления"""
import json
import asyncio

from typing import Any
from dataclasses import dataclass, field
from enum import Enum
import httpx
from app.core.config import settings


class TaskType(Enum):
    SEARCH = "search"
    EXTRACT = "extract"
    COMPARE = "compare"
    VERIFY = "verify"
    SYNTHESIZE = "synthesize"
    GAP_FIND = "gap_find"
    REFINE = "refine"


@dataclass
class SubTask:
    id: str
    type: TaskType
    description: str
    context: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    status: str = "pending"
    parent_id: str | None = None
    depth: int = 0


@dataclass
class ReasoningTrace:
    steps: list[dict[str, Any]] = field(default_factory=list)
    
    def add(self, step: dict[str, Any]):
        self.steps.append(step)
    
    def to_text(self) -> str:
        lines = []
        for i, step in enumerate(self.steps, 1):
            lines.append(f"Шаг {i}: {step.get('action', 'unknown')}")
            lines.append(f"  Результат: {str(step.get('result', ''))[:200]}")
        return "\n".join(lines)


class RLM:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model = "gpt-4o-mini"
        self.trace = ReasoningTrace()
        self.max_depth = 3
        self.max_substacks = 10
    
    async def solve(self, query: str, context: dict[str, Any] = None) -> dict[str, Any]:
        self.trace = ReasoningTrace()
        context = context or {}
        
        analysis = await self._analyze_complexity(query, context)
        self.trace.add({"action": "analyze_complexity", "result": analysis})
        
        if not analysis.get("needs_decomposition", False):
            return await self._direct_answer(query, context)
        
        subtasks = await self._decompose(query, analysis, context)
        self.trace.add({"action": "decompose", "result": f"Создано {len(subtasks)} подзадач"})
        
        results = await self._execute_subtasks(subtasks, context)
        
        sufficiency = await self._check_sufficiency(query, results, context)
        self.trace.add({"action": "check_sufficiency", "result": sufficiency})
        
        if not sufficiency.get("sufficient", False) and sufficiency.get("can_refine", False):
            refined_tasks = await self._refine_tasks(subtasks, results, sufficiency)
            refined_results = await self._execute_subtasks(refined_tasks, context)
            results.extend(refined_results)
        
        final_answer = await self._synthesize(query, results, context)
        
        return {
            "answer": final_answer["text"],
            "sources": final_answer.get("sources", []),
            "reasoning": self.trace.to_text(),
            "confidence": final_answer.get("confidence", 0.5),
            "gaps": sufficiency.get("gaps", []),
            "subtasks_executed": len([r for r in results if r is not None])
        }
    
    async def _analyze_complexity(self, query: str, context: dict) -> dict[str, Any]:
        prompt = f'''Ты — оркестратор интеллектуальной системы. Проанализируй запрос и реши, требуется ли его разбиение на подзадачи.

Запрос: "{query}"

Контекст: {json.dumps(context, ensure_ascii=False)[:500]}

Ответь в формате JSON:
{{
    "needs_decomposition": true,
    "reason": "почему",
    "estimated_subtasks": 4,
    "complexity": "medium",
    "key_aspects": ["аспект 1", "аспект 2"]
}}

Правила:
- needs_decomposition = true, если запрос содержит "и", "сравни", "пробелы", "все методы", "оптимальный"
- needs_decomposition = true, если требуется агрегация из нескольких источников
- needs_decomposition = false, если это простой фактический поиск
'''
        response = await self._call_llm(prompt, temperature=0.1)
        
        try:
            data = json.loads(self._extract_json(response))
            return data
        except :
            needs = any(kw in query.lower() for kw in 
                       ["сравни", "все", "оптимальн", "пробел", "и ", "какие методы"])
            return {
                "needs_decomposition": needs,
                "reason": "fallback heuristic",
                "estimated_subtasks": 3 if needs else 1,
                "complexity": "medium" if needs else "low",
                "key_aspects": []
            }
    
    async def _decompose(self, query: str, analysis: dict, context: dict) -> list[SubTask]:
        prompt = f'''Ты — планировщик задач. Разбей запрос на конкретные подзадачи для исполнителей.

Запрос: "{query}"
Анализ: {json.dumps(analysis, ensure_ascii=False)}

Каждая подзадача должна быть:
- Атомарной (одно действие)
- Измеримой (понятно, что считать результатом)
- Независимой (можно выполнять параллельно)

Доступные типы подзадач:
- search: найти информацию по критериям
- extract: извлечь конкретные данные из найденного
- compare: сравнить два или более варианта
- verify: проверить противоречия
- gap_find: найти недостающую информацию

Ответь в формате JSON:
{{
    "subtasks": [
        {{
            "id": "task_1",
            "type": "search",
            "description": "что делать",
            "parameters": {{"ключ": "значение"}}
        }}
    ]
}}

Максимум {self.max_substacks} подзадач.
'''
        response = await self._call_llm(prompt, temperature=0.2)
        
        try:
            data = json.loads(self._extract_json(response))
            subtasks = []
            for i, st in enumerate(data.get("subtasks", [])):
                subtasks.append(SubTask(
                    id=st.get("id", f"task_{i}"),
                    type=TaskType(st.get("type", "search")),
                    description=st.get("description", ""),
                    context=st.get("parameters", {}),
                    depth=0
                ))
            return subtasks[:self.max_substacks]
        except Exception:
            return [SubTask(
                id="task_fallback",
                type=TaskType.SEARCH,
                description=f"Найти информацию по запросу: {query}",
                context={"query": query},
                depth=0
            )]
    
    async def _execute_subtasks(self, subtasks: list[SubTask], context: dict) -> list[dict]:
        tasks = []
        for st in subtasks:
            tasks.append(self._execute_single_task(st, context))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        processed = []
        for st, result in zip(subtasks, results):
            if isinstance(result, Exception):
                st.status = "failed"
                processed.append({
                    "task_id": st.id,
                    "type": st.type.value,
                    "status": "failed",
                    "error": str(result)
                })
            else:
                st.status = "completed"
                st.result = result
                processed.append({
                    "task_id": st.id,
                    "type": st.type.value,
                    "status": "completed",
                    "result": result
                })
        
        return processed
    
    async def _execute_single_task(self, task: SubTask, context: dict) -> Any:
        if task.type == TaskType.SEARCH:
            return await self._sub_search(task, context)
        elif task.type == TaskType.EXTRACT:
            return await self._sub_extract(task, context)
        elif task.type == TaskType.COMPARE:
            return await self._sub_compare(task, context)
        elif task.type == TaskType.VERIFY:
            return await self._sub_verify(task, context)
        elif task.type == TaskType.GAP_FIND:
            return await self._sub_gap_find(task, context)
        elif task.type == TaskType.REFINE:
            return await self._sub_refine(task, context)
        else:
            return await self._sub_search(task, context)
    
    async def _sub_search(self, task: SubTask, context: dict) -> dict[str, Any]:
        from app.core.services.search import search_service
        
        query = task.context.get("query", task.description)
        search_result = await search_service.search(query, top_k=10)
        
        prompt = f'''Ты — поисковый аналитик. Оцени результаты поиска.

Запрос: {query}
Найдено: {search_result['total_found']} результатов

Результаты (топ-5):
{json.dumps([{'text': r['text'][:300], 'score': r.get('score', 0)} 
            for r in search_result['results'][:5]], ensure_ascii=False)}

Ответь в формате JSON:
{{
    "sufficient": true,
    "key_findings": ["факт 1", "факт 2"],
    "needs_refinement": false,
    "refinement_query": ""
}}
'''
        response = await self._call_llm(prompt, temperature=0.1)
        
        try:
            analysis = json.loads(self._extract_json(response))
        except:
            analysis = {"sufficient": True, "key_findings": [], "needs_refinement": False}
        
        if analysis.get("needs_refinement") and analysis.get("refinement_query"):
            refined_task = SubTask(
                id=f"{task.id}_refined",
                type=TaskType.SEARCH,
                description="Уточнённый поиск",
                context={"query": analysis["refinement_query"]},
                parent_id=task.id,
                depth=task.depth + 1
            )
            if refined_task.depth < self.max_deth:
                refined_result = await self._sub_search(refined_task, context)
                search_result["results"].extend(refined_result.get("results", []))
        
        return {
            "type": "search",
            "query": query,
            "results": search_result,
            "analysis": analysis,
            "task_id": task.id
        }
    
    async def _sub_extract(self, task: SubTask, context: dict) -> dict[str, Any]:
        source_data = task.context.get("source_data", [])
        what_to_extract = task.context.get("extract", "все числовые параметры")
        
        prompt = f'''Ты — извлекатель данных. Извлеки из текста конкретную информацию.

Что извлечь: {what_to_extract}

Данные:
{json.dumps(source_data, ensure_ascii=False)[:3000]}

Ответь в формате JSON:
{{
    "extracted": [
        {{"parameter": "...", "value": "...", "unit": "...", "source": "..."}}
    ],
    "confidence": 0.9
}}
'''
        response = await self._call_llm(prompt, temperature=0.1)
        
        try:
            return json.loads(self._extract_json(response))
        except:
            return {"extracted": [], "confidence": 0}
    
    async def _sub_compare(self, task: SubTask, context: dict) -> dict[str, Any]:
        variants = task.context.get("variants", [])
        criteria = task.context.get("criteria", [])
        
        prompt = f'''Ты — аналитик-сравниватель. Сравни варианты по критериям.

Варианты: {json.dumps(variants, ensure_ascii=False)}
Критерии: {json.dumps(criteria, ensure_ascii=False)}

Ответь в формате JSON:
{{
    "comparison_table": [
        {{"критерий": "...", "вариант_1": "...", "вариант_2": "..."}}
    ],
    "winner": "лучший вариант",
    "reasoning": "почему"
}}
'''
        response = await self._call_llm(prompt, temperature=0.2)
        
        try:
            return json.loads(self._extract_json(response))
        except:
            return {"comparison_table": [], "winner": "unknown", "reasoning": "error"}
    
    async def _sub_verify(self, task: SubTask, context: dict) -> dict[str, Any]:
        facts = task.context.get("facts", [])
        
        prompt = f'''Ты — верификатор. Проверь факты на противоречия.

Факты:
{json.dumps(facts, ensure_ascii=False)}

Ответь в формате JSON:
{{
    "verified": true,
    "contradictions": [],
    "uncertain": [],
    "recommendation": ""
}}
'''
        response = await self._call_llm(prompt, temperature=0.1)
        
        try:
            return json.loads(self._extract_json(response))
        except:
            return {"verified": False, "contradictions": [], "uncertain": [], "recommendation": ""}
    
    async def _sub_gap_find(self, task: SubTask, context: dict) -> dict[str, Any]:
        found_data = task.context.get("found_data", [])
        required_aspects = task.context.get("required", [])
        
        prompt = f'''Ты — аналитик пробелов. Определи, какой информации не хватает.

Найдено:
{json.dumps(found_data, ensure_ascii=False)[:2000]}

Требуемые аспекты:
{json.dumps(required_aspects, ensure_ascii=False)}

Ответь в формате JSON:
{{
    "gaps": [
        {{"aspect": "...", "severity": "critical", "suggestion": "..."}}
    ],
    "coverage_percent": 75
}}
'''
        response = await self._call_llm(prompt, temperature=0.2)
        
        try:
            return json.loads(self._extract_json(response))
        except:
            return {"gaps": [], "coverage_percent": 0}
    
    async def _sub_refine(self, task: SubTask, context: dict) -> dict[str, Any]:
        original_query = task.context.get("original_query", "")
        previous_results = task.context.get("previous_results", [])
        why_refine = task.context.get("reason", "")
        
        prompt = f'''Ты — уточнитель запросов. Сформулируй более точный запрос.

Исходный: {original_query}
Причина уточнения: {why_refine}
Предыдущие результаты: {json.dumps(previous_results, ensure_ascii=False)[:1000]}

Ответь в формате JSON:
{{
    "refined_queries": ["уточнённый запрос 1", "уточнённый запрос 2"],
    "strategy": "описание стратегии"
}}
'''
        response = await self._call_llm(prompt, temperature=0.3)
        
        try:
            return json.loads(self._extract_json(response))
        except:
            return {"refined_queries": [original_query], "strategy": "no change"}
    
    async def _check_sufficiency(self, query: str, results: list[dict], context: dict) -> dict[str, Any]:
        all_findings = []
        for r in results:
            if r.get("status") == "completed":
                result_data = r.get("result", {})
                if isinstance(result_data, dict):
                    findings = result_data.get("analysis", {}).get("key_findings", [])
                    all_findings.extend(findings)
        
        prompt = f'''Ты — оценщик достаточности. Определи, хватает ли данных.

Запрос: {query}
Найдено фактов: {len(all_findings)}
Факты: {json.dumps(all_findings[:10], ensure_ascii=False)}

Ответь в формате JSON:
{{
    "sufficient": true,
    "can_refine": false,
    "gaps": ["чего не хватает"],
    "confidence": 0.8,
    "reasoning": "почему"
}}
'''
        response = await self._call_llm(prompt, temperature=0.1)
        
        try:
            return json.loads(self._extract_json(response))
        except:
            return {
                "sufficient": len(all_findings) > 0,
                "can_refine": len(all_findings) < 3,
                "gaps": ["недостаточно данных"],
                "confidence": 0.3,
                "reasoning": "fallback"
            }
    
    async def _refine_tasks(self, subtasks: list[SubTask], results: list[dict], 
                           sufficiency: dict) -> list[SubTask]:
        gaps = sufficiency.get("gaps", [])
        
        refined = []
        for i, gap in enumerate(gaps[:3]):
            refined.append(SubTask(
                id=f"refined_{i}",
                type=TaskType.REFINE,
                description=f"Уточнение: {gap}",
                context={
                    "original_query": subtasks[0].context.get("query", "") if subtasks else "",
                    "reason": gap,
                    "previous_results": results
                },
                depth=1
            ))
        
        return refined
    
    async def _synthesize(self, query: str, results: list[dict], context: dict) -> dict[str, Any]:
        all_data = []
        sources = []
        
        for r in results:
            if r.get("status") != "completed":
                continue
            
            result = r.get("result", {})
            
            if r.get("type") == "search":
                search_res = result.get("results", {})
                for item in search_res.get("results", []):
                    all_data.append({
                        "text": item.get("text", "")[:500],
                        "score": item.get("score", 0),
                        "doc_id": item.get("doc_id", "")
                    })
                    sources.append({
                        "doc_id": item.get("doc_id", ""),
                        "text": item.get("text", "")[:300]
                    })
            
            elif r.get("type") == "compare":
                all_data.append({
                    "comparison": result.get("comparison_table", []),
                    "winner": result.get("winner", "")
                })
            
            elif r.get("type") == "extract":
                all_data.append({
                    "extracted": result.get("extracted", [])
                })
        
        seen = set()
        unique_sources = []
        for s in sources:
            if s["doc_id"] not in seen:
                seen.add(s["doc_id"])
                unique_sources.append(s)
        
        prompt = f'''Ты — синтезатор ответов. Собери финальный ответ из фрагментов.

Запрос: {query}

Найденные данные:
{json.dumps(all_data, ensure_ascii=False)[:4000]}

Требования:
1. Структурированный ответ с разделами
2. Каждое утверждение подкреплено данными
3. Укажи степень уверенности
4. Если данные противоречивы — скажи об этом
5. Не придумывай информацию

Ответь в формате JSON:
{{
    "text": "полный текст ответа",
    "confidence": 0.8,
    "sources": ["doc_id_1", "doc_id_2"],
    "structure": {{
        "summary": "краткое резюме",
        "details": "детали",
        "gaps": "недостающая информация"
    }}
}}
'''
        response = await self._call_llm(prompt, temperature=0.2)
        
        try:
            data = json.loads(self._extract_json(response))
            return {
                "text": data.get("text", "Не удалось сформировать ответ"),
                "confidence": data.get("confidence", 0.5),
                "sources": unique_sources[:10],
                "structure": data.get("structure", {})
            }
        except:
            texts = [d.get("text", "") for d in all_data if isinstance(d, dict) and "text" in d]
            return {
                "text": "\n\n".join(texts[:5]) if texts else "Данные найдены, но синтез не удался",
                "confidence": 0.3,
                "sources": unique_sources[:5],
                "structure": {}
            }
    
    async def _direct_answer(self, query: str, context: dict) -> dict[str, Any]:
        from app.core.services.search import search_service
        
        search_result = await search_service.search(query, top_k=5)
        texts = [r["text"][:400] for r in search_result.get("results", [])]
        
        prompt = f'''Ответь на вопрос кратко, используя только предоставленные данные.

Вопрос: {query}

Данные:
{chr(10).join(texts)}

Ответь в формате JSON:
{{
    "text": "ответ",
    "confidence": 0.8
}}
'''
        response = await self._call_llm(prompt, temperature=0.1)
        
        try:
            data = json.loads(self._extract_json(response))
            return {
                "answer": data.get("text", "Ответ не найден"),
                "sources": [{"doc_id": r.get("doc_id"), "text": r.get("text", "")[:300]} 
                           for r in search_result.get("results", [])[:5]],
                "reasoning": "Прямой поиск, декомпозиция не требовалась",
                "confidence": data.get("confidence", 0.5),
                "gaps": [],
                "subtasks_executed": 1
            }
        except:
            return {
                "answer": "\n".join(texts[:3]) if texts else "Информация не найдена",
                "sources": [],
                "reasoning": "fallback",
                "confidence": 0.3,
                "gaps": ["ошибка синтеза"],
                "subtasks_executed": 1
            }
    
    async def _call_llm(self, prompt: str, temperature: float = 0.1) -> str:
        if not self.api_key:
            return '{"error": "no API key"}'
        
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
                        {"role": "system", "content": "Ты — компонент рекурсивной системы мышления. Отвечай ТОЛЬКО валидным JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": temperature,
                    "max_tokens": 2000
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    
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


rlm = RLM()