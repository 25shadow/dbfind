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

    if not plan.requires_confirmation:
        return AgentTaskResponse(taskId=None, plan=plan)

    now = datetime.now(UTC).isoformat()
    task_id = uuid4().hex
    AgentTaskRepository().create_task(
        task_id=task_id,
        instruction=payload.instruction.strip(),
        scope=plan.scope,
        file_id=payload.file_id,
        plan=plan,
        status="planned",
        created_at=now,
        logs=[
            _task_log("plan", "completed", "规划完成"),
        ],
    )

    return AgentTaskResponse(taskId=task_id, plan=plan)


@router.post("/tasks/{task_id}/run-query", response_model=AgentTaskItem)
async def run_agent_query_stage(task_id: str) -> AgentTaskItem:
    repository = AgentTaskRepository()
    try:
        task = repository.get_task(task_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Agent 任务不存在") from exc

    repository.update_task(
        task_id,
        status="querying",
        error=None,
        log=_task_log("query", "running", "正在查询数据"),
        updated_at=datetime.now(UTC).isoformat(),
    )
    try:
        preview = AgentExecutionService().preview(plan=task["plan"], file_id=task["file_id"])
    except FileNotFoundError as exc:
        task = repository.update_task(
            task_id,
            status="failed",
            error="文件不存在",
            log=_task_log("query", "failed", "查询失败：文件不存在"),
            updated_at=datetime.now(UTC).isoformat(),
        )
        raise HTTPException(status_code=404, detail="文件不存在") from exc
    except ValueError as exc:
        task = repository.update_task(
            task_id,
            status="failed",
            error=str(exc),
            log=_task_log("query", "failed", f"查询失败：{exc}"),
            updated_at=datetime.now(UTC).isoformat(),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    first_sheet = preview.sheets[0] if preview.sheets else None
    query_result = {
        "columns": first_sheet.columns if first_sheet else [],
        "rows": first_sheet.rows if first_sheet else [],
        "rowCount": first_sheet.row_count if first_sheet else 0,
    }
    task = repository.update_task(
        task_id,
        status="awaiting_confirmation",
        error=None,
        query_result=query_result,
        preview=preview,
        sources=preview.sources,
        log=_task_log("query", "completed", "查询完成，等待确认生成工作簿"),
        updated_at=datetime.now(UTC).isoformat(),
    )
    task = repository.update_task(
        task_id,
        status="awaiting_confirmation",
        error=None,
        log=_task_log("preview", "completed", "查询结果和来源已生成"),
        updated_at=datetime.now(UTC).isoformat(),
    )
    return _task_item(task)


@router.post("/preview", response_model=AgentOperationPreview)
async def preview_agent_plan(payload: AgentPreviewRequest) -> AgentOperationPreview:
    repository = AgentTaskRepository()
    try:
        result = AgentExecutionService().preview(plan=payload.plan, file_id=payload.file_id)
        if payload.task_id:
            repository.update_task(
                payload.task_id,
                status="needs_confirmation",
                error=None,
                log=_task_log("preview", "completed", "操作预览已生成，等待确认执行"),
                updated_at=datetime.now(UTC).isoformat(),
            )
        return result
    except FileNotFoundError as exc:
        if payload.task_id:
            repository.update_task(
                payload.task_id,
                status="needs_revision",
                error="文件不存在",
                log=_task_log("preview", "failed", "预览失败：文件不存在"),
                updated_at=datetime.now(UTC).isoformat(),
            )
        raise HTTPException(status_code=404, detail="文件不存在") from exc
    except ValueError as exc:
        if payload.task_id:
            repository.update_task(
                payload.task_id,
                status="needs_revision",
                error=str(exc),
                log=_task_log("preview", "failed", f"预览失败：{exc}"),
                updated_at=datetime.now(UTC).isoformat(),
            )
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/execute", response_model=AgentExecuteResponse)
async def execute_agent_plan(payload: AgentExecuteRequest) -> AgentExecuteResponse:
    repository = AgentTaskRepository()
    if payload.task_id:
        try:
            task = repository.get_task(payload.task_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Agent 任务不存在") from exc
        if task["status"] not in {"awaiting_confirmation", "completed"}:
            raise HTTPException(status_code=400, detail="请先完成查询并确认来源后再生成工作簿")
        repository.update_task(
            payload.task_id,
            status="executing",
            error=None,
            log=_task_log("execute", "running", "开始执行并生成工作簿"),
            updated_at=datetime.now(UTC).isoformat(),
        )
    try:
        result = AgentExecutionService().execute(plan=payload.plan, file_id=payload.file_id)
    except FileNotFoundError as exc:
        if payload.task_id:
            repository.update_task(
                payload.task_id,
                status="failed",
                error="文件不存在",
                log=_task_log("execute", "failed", "执行失败：文件不存在"),
                updated_at=datetime.now(UTC).isoformat(),
            )
        raise HTTPException(status_code=404, detail="文件不存在") from exc
    except ValueError as exc:
        if payload.task_id:
            repository.update_task(
                payload.task_id,
                status="failed",
                error=str(exc),
                log=_task_log("execute", "failed", f"执行失败：{exc}"),
                updated_at=datetime.now(UTC).isoformat(),
            )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if payload.task_id:
        repository.update_task(
            payload.task_id,
            status=result.status,
            output_id=result.output_id,
            download_url=result.download_url,
            error=None,
            log=_task_log("execute", "completed", "工作簿已生成"),
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
        logs=task.get("logs", []),
        queryResult=task.get("query_result"),
        previewResult=task.get("preview"),
        sources=task.get("sources", []),
        createdAt=task["created_at"],
        updatedAt=task["updated_at"],
    )


def _task_log(stage: str, status: str, message: str) -> dict:
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "stage": stage,
        "status": status,
        "message": message,
    }


def _agent_error_detail(message: str) -> str:
    if "Invalid JSON" in message or "结构化计划不合法" in message:
        return "OpenAI Agents SDK 返回了不合法的结构化计划，请调整任务描述后重试。"
    if len(message) > 300:
        return f"{message[:300]}..."
    return message
