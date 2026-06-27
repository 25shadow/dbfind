from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from starlette.status import HTTP_204_NO_CONTENT

from app.schemas.query import QueryRequest, QueryResponse
from app.adapters.ai_adapter import AiResponseError
from app.services.query_service import QueryService

router = APIRouter()


@router.post("", response_model=QueryResponse)
async def create_query(payload: QueryRequest) -> QueryResponse:
    try:
        return await run_in_threadpool(QueryService().run, payload)
    except AiResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/history", response_model=list[QueryResponse])
async def list_query_history(keyword: str | None = None) -> list[QueryResponse]:
    return await run_in_threadpool(QueryService().list_history, keyword)


@router.get("/{query_id}", response_model=QueryResponse)
async def get_query(query_id: str) -> QueryResponse:
    try:
        return await run_in_threadpool(QueryService().get, query_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="查询不存在") from exc


@router.delete("/{query_id}", status_code=HTTP_204_NO_CONTENT)
async def delete_query(query_id: str) -> None:
    try:
        await run_in_threadpool(QueryService().delete, query_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="查询不存在") from exc
