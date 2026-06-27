from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.query import QueryResponse


def test_create_query_runs_service_in_threadpool(monkeypatch, temp_workspace):
    calls = []

    async def fake_run_in_threadpool(function, *args, **kwargs):
        calls.append((function.__name__, args, kwargs))
        return QueryResponse(
            queryId="query_1",
            fileId="file_1",
            scope="selected",
            question="查一下",
            sql='SELECT 1 AS "value";',
            columns=["value"],
            rows=[{"value": 1}],
            explanation="查询已完成。",
            createdAt="2026-06-27T00:00:00+00:00",
            initialSql='SELECT 1 AS "value";',
            repairError=None,
            repairedSql=None,
            wasRepaired=False,
            sources=[],
        )

    monkeypatch.setattr("app.api.routes.query.run_in_threadpool", fake_run_in_threadpool)

    response = TestClient(create_app()).post(
        "/api/query",
        json={"question": "查一下", "scope": "selected", "fileId": "file_1"},
    )

    assert response.status_code == 200
    assert response.json()["queryId"] == "query_1"
    assert len(calls) == 1
    function_name, args, kwargs = calls[0]
    assert function_name == "run"
    assert args[0].question == "查一下"
    assert kwargs == {}
