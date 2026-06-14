from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from starlette.status import HTTP_204_NO_CONTENT

from app.repositories.agent_task_repository import AgentTaskRepository
from app.schemas.agent import (
    AgentExecuteRequest,
    AgentExecuteResponse,
    AgentOperationPreview,
    AgentPreviewRequest,
    AgentRequest,
    AgentTaskItem,
    AgentTaskListResponse,
    AgentTaskResponse,
)
from app.services.agent_execution_service import AgentExecutionService
from app.services.agent_service import AgentService

router = APIRouter()


@router.post("/plan", response_model=AgentTaskResponse)
async def create_agent_plan(payload: AgentRequest) -> AgentTaskResponse:
    try:
        plan = await AgentService().plan(
            instruction=payload.instruction,
            scope=payload.scope,
            file_id=payload.file_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=_agent_error_detail(str(exc))) from exc

    now = datetime.now(UTC).isoformat()
    task_id = uuid4().hex
    status = "needs_confirmation" if plan.requires_confirmation else "completed"
    AgentTaskRepository().create_task(
        task_id=task_id,
        instruction=payload.instruction.strip(),
        scope=plan.scope,
        file_id=payload.file_id,
        plan=plan,
        status=status,
        created_at=now,
    )

    return AgentTaskResponse(taskId=task_id, plan=plan)


@router.post("/preview", response_model=AgentOperationPreview)
async def preview_agent_plan(payload: AgentPreviewRequest) -> AgentOperationPreview:
    repository = AgentTaskRepository()
    try:
        return AgentExecutionService().preview(plan=payload.plan, file_id=payload.file_id)
    except FileNotFoundError as exc:
        if payload.task_id:
            repository.update_task(payload.task_id, status="failed", error="文件不存在")
        raise HTTPException(status_code=404, detail="文件不存在") from exc
    except ValueError as exc:
        if payload.task_id:
            repository.update_task(payload.task_id, status="failed", error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/execute", response_model=AgentExecuteResponse)
async def execute_agent_plan(payload: AgentExecuteRequest) -> AgentExecuteResponse:
    repository = AgentTaskRepository()
    try:
        result = AgentExecutionService().execute(plan=payload.plan, file_id=payload.file_id)
    except FileNotFoundError as exc:
        if payload.task_id:
            repository.update_task(payload.task_id, status="failed", error="文件不存在")
        raise HTTPException(status_code=404, detail="文件不存在") from exc
    except ValueError as exc:
        if payload.task_id:
            repository.update_task(payload.task_id, status="failed", error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if payload.task_id:
        repository.update_task(
            payload.task_id,
            status=result.status,
            output_id=result.output_id,
            download_url=result.download_url,
            error=None,
            updated_at=datetime.now(UTC).isoformat(),
        )
    return result


@router.get("/tasks", response_model=AgentTaskListResponse)
async def list_agent_tasks() -> AgentTaskListResponse:
    return AgentTaskListResponse(
        tasks=[_task_item(task) for task in AgentTaskRepository().list_tasks()]
    )


@router.get("/tasks/{task_id}", response_model=AgentTaskItem)
async def get_agent_task(task_id: str) -> AgentTaskItem:
    try:
        return _task_item(AgentTaskRepository().get_task(task_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Agent 任务不存在") from exc


@router.delete("/tasks/{task_id}", status_code=HTTP_204_NO_CONTENT)
async def delete_agent_task(task_id: str) -> None:
    try:
        AgentTaskRepository().delete_task(task_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Agent 任务不存在") from exc


@router.get("/generated/{output_id}")
async def get_generated_workbook(output_id: str) -> FileResponse:
    try:
        output_path = AgentExecutionService().generated_path(output_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="生成文件不存在") from exc

    return FileResponse(
        output_path,
        filename=f"dbfind-agent-{output_id}",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _task_item(task: dict) -> AgentTaskItem:
    return AgentTaskItem(
        id=task["id"],
        instruction=task["instruction"],
        scope=task["scope"],
        fileId=task["file_id"],
        plan=task["plan"],
        status=task["status"],
        outputId=task["output_id"],
        downloadUrl=task["download_url"],
        error=task["error"],
        createdAt=task["created_at"],
        updatedAt=task["updated_at"],
    )


def _agent_error_detail(message: str) -> str:
    if "Invalid JSON" in message or "结构化计划不合法" in message:
        return "OpenAI Agents SDK 返回了不合法的结构化计划，请调整任务描述后重试。"
    if len(message) > 300:
        return f"{message[:300]}..."
    return message
