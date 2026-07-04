"""API endpoints для поиска и ответов"""

from fastapi import APIRouter, HTTPException

from ...core.schemas import SearchRequest, SearchResponse, AnswerRequest, AnswerResponse, GraphResponse
from ...core.services.search import search_service
from ...core.services.rlm import rlm

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/", response_model=SearchResponse)
def search(request: SearchRequest):
    """Гибридный поиск по корпусу"""
    try:
        result = search_service.search(
            query=request.query,
            top_k=request.top_k,
            filters=request.filters
        )
        return SearchResponse(**result)
    except Exception as e:
        raise HTTPException(500, f"Ошибка поиска: {str(e)}")


@router.post("/answer", response_model=AnswerResponse)
def answer(request: AnswerRequest):
    """
    Полный ответ на вопрос с источниками и графом.
    MVP-реализация: поиск + простая агрегация.
    """
    return rlm.solve(request.query)

    # # Поиск фактов
    # search_result = search_service.search(request.query, top_k=10)
    
    # # Формируем контекст для ответа
    # facts = []
    # sources = []
    
    # for r in search_result["results"]:
    #     facts.append(r["text"])
    #     sources.append({
    #         "doc_id": r["doc_id"],
    #         "text": r["text"][:300],
    #         "chunk_index": r["chunk_index"],
    #         "score": r["score"]
    #     })
    

    # # Простой ответ для MVP (без LLM-синтеза, чтобы не зависеть от API)
    # answer_text = _simple_synthesize(request.query, search_result["results"])
 
    # # Граф связанных сущностей
    # graph = None
    # if request.include_graph and search_result.get("query_entities"):
    #     graph = graph_service.get_subgraph_for_entities(
    #         search_result["query_entities"],
    #         depth=2
    #     )
    
    # return AnswerResponse(
    #     answer=answer_text,
    #     sources=sources,
    #     related_entities=[{"name": e} for e in search_result.get("query_entities", [])],
    #     gaps=_detect_gaps(search_result),
    #     graph=GraphResponse(**graph) if graph else None
    # )


def _simple_synthesize(query: str, results: list) -> str:
    """Простая агрегация результатов для MVP"""
    if not results:
        return "По запросу не найдено релевантных документов."
    
    parts = ["## Найденная информация\n"]
    
    # Группировка по типу результата
    vector_results = [r for r in results if r.get("type") == "vector"]
    graph_results = [r for r in results if r.get("type") == "graph"]
    
    if vector_results:
        parts.append("### Прямые совпадения\n")
        for i, r in enumerate(vector_results[:5], 1):
            parts.append(f"{i}. {r['text'][:400]}...\n")
            parts.append(f"   *Источник: документ {r['doc_id']}, фрагмент {r['chunk_index']}*\n")
    
    if graph_results:
        parts.append("\n### Связанные данные из графа\n")
        for r in graph_results[:3]:
            parts.append(f"- {r.get('path', 'связанная сущность')}: {r['text'][:300]}...\n")
    
    # Статистика
    parts.append(f"\n---\n*Всего найдено: {len(results)} релевантных фрагментов*")
    
    return "\n".join(parts)


def _detect_gaps(search_result: dict) -> list:
    """Выявить простые пробелы для MVP"""
    gaps = []
    query_lower = search_result.get("query", "").lower()
    
    # Простые эвристики
    if "холодный климат" in query_lower or "север" in query_lower:
        cold_results = [r for r in search_result.get("results", []) 
                       if "холод" in r.get("text", "").lower() or "север" in r.get("text", "").lower()]
        if len(cold_results) < 3:
            gaps.append("Мало данных по применению в холодном климате")
    
    if "экономическ" in query_lower or "стоимост" in query_lower:
        econ_results = [r for r in search_result.get("results", [])
                       if any(w in r.get("text", "").lower() for w in ["стоимость", "затраты", "капекс", "opex", "руб", "$"])]
        if len(econ_results) == 0:
            gaps.append("Отсутствуют технико-экономические оценки")
    
    if not gaps:
        gaps.append("Для детального анализа пробелов требуется экспертная верификация")
    
    return gaps