"""API endpoints для поиска и ответов"""

from fastapi import APIRouter, HTTPException

from ...core.schemas import SearchRequest, SearchResponse, AnswerRequest, AnswerResponse, GraphResponse
from ...core.services.search import search_service
from ...core.services.graph import graph_service

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
    """
    # Поиск фактов
    search_result = search_service.search(request.query, top_k=10)
    response = rlm.solve(request.query)

    graph = None
    if request.include_graph and search_result.get("query_entities"):
        graph = graph_service.get_subgraph_for_entities(
            search_result["query_entities"],
            depth=2
        )

    answer = AnswerResponse(
        answer=response.get("answer", ""),
        sources=response.get("sources", []),
        related_entities=response.get("related_entities", []),
        gaps=response.get("gaps", []),
        graph=GraphResponse(**graph) if graph else None
    )

    return answer 
