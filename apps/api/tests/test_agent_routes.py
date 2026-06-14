from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.schemas.agent import AgentExecuteResponse, AgentPlan, AgentPreview, AgentStep

from app.main import create_app


def test_agent_plan_route_returns_502_when_sdk_plan_fails(temp_workspace):
    client = TestClient(create_app())

    response = client.post(
        "/api/agent/plan",
        json={"instruction": "清洗全部表格", "scope": "all"},
    )

    assert response.status_code == 502
    assert "OpenAI Agents SDK" in response.json()["detail"]


def test_agent_plan_route_summarizes_verbose_sdk_json_error(temp_workspace):
    client = TestClient(create_app())
    verbose_error = (
        'OpenAI Agents SDK 执行失败: Invalid JSON when parsing {"intent":"excel_operation",'
        '"preview":{"affectedColumns":["市别","街道_Number"]},"sampleBeforeAfter":'
        '["Before query, you will see all 22 rows with all 11 columns."],"steps":[]}'
    )

    with patch("app.api.routes.agent.AgentService") as service_class:
        service_class.return_value.plan = AsyncMock(side_effect=RuntimeError(verbose_error))
        response = client.post(
            "/api/agent/plan",
            json={"instruction": "生成表格", "scope": "all"},
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "OpenAI Agents SDK 返回了不合法的结构化计划，请调整任务描述后重试。"


def test_agent_execute_route_returns_generated_file_metadata(temp_workspace):
    client = TestClient(create_app())

    with patch("app.api.routes.agent.AgentExecutionService") as service_class:
        service = service_class.return_value
        service.execute.return_value = AgentExecuteResponse(
            status="completed",
            outputId="agent.xlsx",
            fileName="dbfind-agent-agent.xlsx",
            downloadUrl="/api/agent/generated/agent.xlsx",
        )

        response = client.post(
            "/api/agent/execute",
            json={
                "fileId": "file-1",
                "plan": {
                    "intent": "excel_operation",
                    "scope": "selected",
                    "summary": "生成工作簿",
                    "requiresConfirmation": True,
                    "riskLevel": "medium",
                    "steps": [
                        {
                            "tool": "workbook_writer",
                            "purpose": "生成工作簿",
                            "params": "",
                        }
                    ],
                    "preview": {
                        "affectedRows": None,
                        "affectedColumns": [],
                        "sampleBeforeAfter": [],
                    },
                    "status": "draft",
                },
            },
        )

    assert response.status_code == 200
    assert response.json()["downloadUrl"] == "/api/agent/generated/agent.xlsx"
    service.execute.assert_called_once()


def test_agent_plan_route_persists_task_and_returns_task_id(temp_workspace):
    client = TestClient(create_app())
    plan = AgentPlan(
        intent="excel_operation",
        scope="all",
        summary="生成工作簿",
        requiresConfirmation=True,
        riskLevel="medium",
        steps=[AgentStep(tool="workbook_writer", purpose="写出", params={})],
        preview=AgentPreview(),
    )

    with patch("app.api.routes.agent.AgentService") as service_class:
        service_class.return_value.plan = AsyncMock(return_value=plan)
        response = client.post(
            "/api/agent/plan",
            json={"instruction": "生成工作簿", "scope": "all"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["taskId"]
    assert body["plan"]["summary"] == "生成工作簿"

    tasks = client.get("/api/agent/tasks").json()["tasks"]
    assert tasks[0]["id"] == body["taskId"]
    assert tasks[0]["status"] == "needs_confirmation"


def test_agent_execute_route_updates_existing_task(temp_workspace):
    client = TestClient(create_app())
    plan_payload = {
        "intent": "excel_operation",
        "scope": "all",
        "summary": "生成工作簿",
        "requiresConfirmation": True,
        "riskLevel": "medium",
        "steps": [{"tool": "workbook_writer", "purpose": "写出", "params": ""}],
        "preview": {"affectedRows": None, "affectedColumns": [], "sampleBeforeAfter": []},
        "status": "draft",
    }

    with patch("app.api.routes.agent.AgentService") as service_class:
        service_class.return_value.plan = AsyncMock(return_value=AgentPlan.model_validate(plan_payload))
        plan_response = client.post(
            "/api/agent/plan",
            json={"instruction": "生成工作簿", "scope": "all"},
        )
    task_id = plan_response.json()["taskId"]

    with patch("app.api.routes.agent.AgentExecutionService") as service_class:
        service = service_class.return_value
        service.execute.return_value = AgentExecuteResponse(
            status="completed",
            outputId="agent.xlsx",
            fileName="dbfind-agent-agent.xlsx",
            downloadUrl="/api/agent/generated/agent.xlsx",
        )
        response = client.post(
            "/api/agent/execute",
            json={"taskId": task_id, "fileId": None, "plan": plan_payload},
        )

    assert response.status_code == 200
    task = client.get(f"/api/agent/tasks/{task_id}").json()
    assert task["status"] == "completed"
    assert task["outputId"] == "agent.xlsx"
    assert task["downloadUrl"] == "/api/agent/generated/agent.xlsx"


def test_agent_task_route_deletes_existing_task(temp_workspace):
    client = TestClient(create_app())
    plan_payload = {
        "intent": "excel_operation",
        "scope": "all",
        "summary": "生成工作簿",
        "requiresConfirmation": True,
        "riskLevel": "medium",
        "steps": [{"tool": "workbook_writer", "purpose": "写出", "params": ""}],
        "preview": {"affectedRows": None, "affectedColumns": [], "sampleBeforeAfter": []},
        "status": "draft",
    }

    with patch("app.api.routes.agent.AgentService") as service_class:
        service_class.return_value.plan = AsyncMock(return_value=AgentPlan.model_validate(plan_payload))
        plan_response = client.post(
            "/api/agent/plan",
            json={"instruction": "生成工作簿", "scope": "all"},
        )
    task_id = plan_response.json()["taskId"]

    response = client.delete(f"/api/agent/tasks/{task_id}")

    assert response.status_code == 204
    assert client.get(f"/api/agent/tasks/{task_id}").status_code == 404


def test_agent_task_route_returns_404_when_deleting_missing_task(temp_workspace):
    client = TestClient(create_app())

    response = client.delete("/api/agent/tasks/missing-task")

    assert response.status_code == 404


def test_agent_preview_route_updates_task_when_preview_fails(temp_workspace):
    client = TestClient(create_app())
    plan_payload = {
        "intent": "excel_operation",
        "scope": "all",
        "summary": "生成工作簿",
        "requiresConfirmation": True,
        "riskLevel": "medium",
        "steps": [{"tool": "workbook_writer", "purpose": "写出", "params": ""}],
        "preview": {"affectedRows": None, "affectedColumns": [], "sampleBeforeAfter": []},
        "status": "draft",
    }

    with patch("app.api.routes.agent.AgentService") as service_class:
        service_class.return_value.plan = AsyncMock(return_value=AgentPlan.model_validate(plan_payload))
        plan_response = client.post(
            "/api/agent/plan",
            json={"instruction": "生成工作簿", "scope": "all"},
        )
    task_id = plan_response.json()["taskId"]

    with patch("app.api.routes.agent.AgentExecutionService") as service_class:
        service_class.return_value.preview.side_effect = ValueError("字段不存在: 金额")
        response = client.post(
            "/api/agent/preview",
            json={"taskId": task_id, "fileId": None, "plan": plan_payload},
        )

    assert response.status_code == 400
    task = client.get(f"/api/agent/tasks/{task_id}").json()
    assert task["status"] == "failed"
    assert task["error"] == "字段不存在: 金额"
