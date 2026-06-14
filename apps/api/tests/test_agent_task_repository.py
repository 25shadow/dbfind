from datetime import UTC, datetime
import sqlite3

from app.repositories.agent_task_repository import AgentTaskRepository
from app.schemas.agent import AgentPlan, AgentPreview, AgentStep


def _plan() -> AgentPlan:
    return AgentPlan(
        intent="excel_operation",
        scope="all",
        summary="生成汇总工作簿",
        requiresConfirmation=True,
        riskLevel="medium",
        steps=[AgentStep(tool="workbook_writer", purpose="写出新工作簿", params={})],
        preview=AgentPreview(),
    )


def test_agent_task_repository_creates_and_updates_task(temp_workspace):
    repository = AgentTaskRepository()
    created_at = datetime.now(UTC).isoformat()

    task = repository.create_task(
        task_id="task-1",
        instruction="生成汇总工作簿",
        scope="all",
        file_id=None,
        plan=_plan(),
        status="needs_confirmation",
        created_at=created_at,
    )

    assert task["id"] == "task-1"
    assert task["plan"].summary == "生成汇总工作簿"
    assert task["status"] == "needs_confirmation"

    repository.update_task(
        "task-1",
        status="completed",
        output_id="out.xlsx",
        download_url="/api/agent/generated/out.xlsx",
    )

    updated = repository.get_task("task-1")
    assert updated["status"] == "completed"
    assert updated["output_id"] == "out.xlsx"
    assert updated["download_url"] == "/api/agent/generated/out.xlsx"
    assert repository.list_tasks()[0]["id"] == "task-1"


def test_agent_task_repository_skips_invalid_historical_task(temp_workspace):
    repository = AgentTaskRepository()
    created_at = datetime.now(UTC).isoformat()

    repository.create_task(
        task_id="task-valid",
        instruction="生成汇总工作簿",
        scope="all",
        file_id=None,
        plan=_plan(),
        status="needs_confirmation",
        created_at=created_at,
    )

    with sqlite3.connect(temp_workspace / "meta.db") as conn:
        conn.execute(
            """
            INSERT INTO agent_tasks (
                id, instruction, scope, file_id, plan_json, status,
                output_id, download_url, error, created_at, updated_at
            )
            VALUES (?, ?, ?, NULL, ?, ?, NULL, NULL, NULL, ?, ?)
            """,
            (
                "task-invalid",
                "坏历史记录",
                "all",
                '{"intent":"excel_operation","scope":"all","summary":"坏计划","requiresConfirmation":true,"riskLevel":"medium","steps":[{"tool":"query","purpose":"查询","params":"question"}],"preview":{}}',
                "failed",
                created_at,
                created_at,
            ),
        )

    tasks = repository.list_tasks()

    assert [task["id"] for task in tasks] == ["task-valid"]


def test_agent_task_repository_deletes_task(temp_workspace):
    repository = AgentTaskRepository()
    created_at = datetime.now(UTC).isoformat()
    repository.create_task(
        task_id="task-delete",
        instruction="生成汇总工作簿",
        scope="all",
        file_id=None,
        plan=_plan(),
        status="needs_confirmation",
        created_at=created_at,
    )

    repository.delete_task("task-delete")

    assert repository.list_tasks() == []
    try:
        repository.get_task("task-delete")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("deleted task should not exist")
