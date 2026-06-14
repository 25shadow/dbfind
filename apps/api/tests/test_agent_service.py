import pytest

from app.services.agent_service import AgentService
from app.schemas.agent import AgentPlan, AgentPreview, AgentStep


class FakePlanner:
    def __init__(self) -> None:
        self.calls = []

    async def plan(
        self,
        instruction: str,
        scope: str,
        file_id: str | None,
        schema_context: str = "",
    ) -> AgentPlan | None:
        self.calls.append(
            {
                "instruction": instruction,
                "scope": scope,
                "file_id": file_id,
                "schema_context": schema_context,
            }
        )
        return AgentPlan(
            intent="excel_operation",
            scope=scope,
            summary=f"SDK planned: {instruction}",
            requiresConfirmation=True,
            riskLevel="medium",
            steps=[
                AgentStep(
                    tool="workbook_writer",
                    purpose="write via sdk plan",
                    params={"fileId": file_id},
                )
            ],
            preview=AgentPreview(),
        )


class EmptyPlanner:
    async def plan(
        self,
        instruction: str,
        scope: str,
        file_id: str | None,
        schema_context: str = "",
    ) -> AgentPlan | None:
        return None


class FakeSchemaService:
    def build_schema_text(self, file_id: str) -> str:
        return f'selected-schema:{file_id}: "城市" "街道数量"'

    def build_relevant_all_files_schema_text(self, question: str) -> str:
        return f'all-schema:{question}: "城市" "街道数量"'


class InvalidParamsPlanner:
    async def plan(
        self,
        instruction: str,
        scope: str,
        file_id: str | None,
        schema_context: str = "",
    ) -> AgentPlan | None:
        return AgentPlan(
            intent="excel_operation",
            scope=scope,
            summary="bad plan",
            requiresConfirmation=True,
            riskLevel="medium",
            steps=[
                AgentStep(
                    tool="query",
                    purpose="查询",
                    params={"operations": []},
                ),
                AgentStep(
                    tool="dataframe_transform",
                    purpose="聚合",
                    params={
                        "operations": [
                            {
                                "type": "groupby_agg",
                                "by": ["城市"],
                                "aggregations": [{"column": "金额", "agg": "sum"}],
                            }
                        ]
                    },
                ),
            ],
            preview=AgentPreview(),
        )


class InvalidStyleParamsPlanner:
    async def plan(
        self,
        instruction: str,
        scope: str,
        file_id: str | None,
        schema_context: str = "",
    ) -> AgentPlan | None:
        return AgentPlan(
            intent="excel_operation",
            scope=scope,
            summary="bad style plan",
            requiresConfirmation=True,
            riskLevel="medium",
            steps=[
                AgentStep(
                    tool="query",
                    purpose="查询",
                    params={"question": instruction, "scope": scope},
                ),
                AgentStep(
                    tool="workbook_style",
                    purpose="样式",
                    params={"styles": ["asTable"]},
                ),
            ],
            preview=AgentPreview(),
        )


class InvalidOperationsStringPlanner:
    async def plan(
        self,
        instruction: str,
        scope: str,
        file_id: str | None,
        schema_context: str = "",
    ) -> AgentPlan | None:
        return AgentPlan(
            intent="excel_operation",
            scope=scope,
            summary="bad operations plan",
            requiresConfirmation=True,
            riskLevel="medium",
            steps=[
                AgentStep(
                    tool="query",
                    purpose="查询",
                    params={"question": instruction, "scope": scope},
                ),
                AgentStep(
                    tool="dataframe_transform",
                    purpose="聚合",
                    params={"operations": "[]"},
                ),
            ],
            preview=AgentPreview(),
        )


@pytest.mark.anyio
async def test_agent_plan_for_table_operation_requires_confirmation(temp_workspace):
    service = AgentService(planner=FakePlanner(), schema_service=FakeSchemaService())

    plan = await service.plan(
        instruction="整理当前表格，清洗空值并生成一个适合汇报的新工作簿",
        scope="selected",
        file_id="file-1",
    )

    assert plan.intent == "excel_operation"
    assert plan.requires_confirmation is True
    assert plan.risk_level == "medium"
    assert [step.tool for step in plan.steps] == ["workbook_writer"]
    assert "SDK planned" in plan.summary


@pytest.mark.anyio
async def test_agent_service_fast_plans_common_workbook_generation(temp_workspace):
    planner = FakePlanner()
    service = AgentService(planner=planner, schema_service=FakeSchemaService())

    plan = await service.plan(
        instruction="把广东省广州市街道数量和韶关街道数量做一个对比并生成表格",
        scope="all",
        file_id=None,
    )

    assert planner.calls == []
    assert plan.intent == "excel_operation"
    assert plan.requires_confirmation is True
    assert [step.tool for step in plan.steps] == ["query", "workbook_writer", "workbook_style"]
    assert plan.steps[0].params


@pytest.mark.anyio
async def test_agent_service_fast_plans_selected_comparison_workbook_generation(temp_workspace):
    planner = FakePlanner()
    service = AgentService(planner=planner, schema_service=FakeSchemaService())

    plan = await service.plan(
        instruction="把广东省广州街道数量和韶关街道数量做一个对比并且生成表格，并做一个减法，看他们的街道数量差距多少",
        scope="selected",
        file_id="file-1",
    )

    assert planner.calls == []
    assert plan.scope == "selected"
    assert plan.intent == "excel_operation"
    assert [step.tool for step in plan.steps] == ["query", "workbook_writer", "workbook_style"]


@pytest.mark.anyio
async def test_agent_plan_for_query_uses_query_tool_without_write_confirmation(temp_workspace):
    class QueryPlanner:
        async def plan(
            self,
            instruction: str,
            scope: str,
            file_id: str | None,
            schema_context: str = "",
        ) -> AgentPlan | None:
            return AgentPlan(
                intent="query",
                scope=scope,
                summary="SDK query plan",
                requiresConfirmation=False,
                riskLevel="low",
                steps=[
                        AgentStep(
                            tool="query",
                            purpose="query via sdk plan",
                            params={"question": instruction, "scope": scope},
                        )
                ],
                preview=AgentPreview(),
            )

    service = AgentService(planner=QueryPlanner(), schema_service=FakeSchemaService())

    plan = await service.plan(
        instruction="查询全部文件中销售额最高的记录",
        scope="all",
        file_id=None,
    )

    assert plan.intent == "query"
    assert plan.requires_confirmation is False
    assert plan.risk_level == "low"
    assert [step.tool for step in plan.steps] == ["query"]
    assert plan.scope == "all"


@pytest.mark.anyio
async def test_agent_plan_rejects_selected_scope_without_file(temp_workspace):
    service = AgentService(planner=FakePlanner(), schema_service=FakeSchemaService())

    with pytest.raises(ValueError, match="请选择一个已导入的文件"):
        await service.plan(
            instruction="清洗当前表格",
            scope="selected",
            file_id=None,
        )


@pytest.mark.anyio
async def test_agent_service_uses_injected_sdk_planner_result(temp_workspace):
    service = AgentService(planner=FakePlanner(), schema_service=FakeSchemaService())

    plan = await service.plan(
        instruction="生成一个格式化工作簿",
        scope="selected",
        file_id="file-1",
    )

    assert plan.summary == "SDK planned: 生成一个格式化工作簿"
    assert [step.tool for step in plan.steps] == ["workbook_writer"]


@pytest.mark.anyio
async def test_agent_service_requires_openai_agents_sdk_plan(temp_workspace):
    service = AgentService(planner=EmptyPlanner(), schema_service=FakeSchemaService())

    with pytest.raises(RuntimeError, match="OpenAI Agents SDK"):
        await service.plan(
            instruction="清洗当前范围",
            scope="all",
            file_id=None,
        )


@pytest.mark.anyio
async def test_agent_service_passes_selected_file_schema_context(temp_workspace):
    planner = FakePlanner()
    service = AgentService(planner=planner, schema_service=FakeSchemaService())

    await service.plan(
        instruction="生成城市街道数量工作簿",
        scope="selected",
        file_id="file-1",
    )

    assert planner.calls[0]["schema_context"] == 'selected-schema:file-1: "城市" "街道数量"'


@pytest.mark.anyio
async def test_agent_service_passes_relevant_all_files_schema_context(temp_workspace):
    planner = FakePlanner()
    service = AgentService(planner=planner, schema_service=FakeSchemaService())

    await service.plan(
        instruction="生成城市街道数量工作簿",
        scope="all",
        file_id=None,
    )

    assert planner.calls[0]["schema_context"] == 'all-schema:生成城市街道数量工作簿: "城市" "街道数量"'


@pytest.mark.anyio
async def test_agent_service_rejects_invalid_tool_params_before_task_creation(temp_workspace):
    service = AgentService(planner=InvalidParamsPlanner(), schema_service=FakeSchemaService())

    with pytest.raises(RuntimeError, match="query.params"):
        await service.plan(
            instruction="生成城市汇总工作簿",
            scope="all",
            file_id=None,
        )


@pytest.mark.anyio
async def test_agent_service_rejects_operations_string_params(temp_workspace):
    service = AgentService(planner=InvalidOperationsStringPlanner(), schema_service=FakeSchemaService())

    with pytest.raises(RuntimeError, match="operations"):
        await service.plan(
            instruction="生成城市汇总工作簿",
            scope="all",
            file_id=None,
        )


@pytest.mark.anyio
async def test_agent_service_rejects_wrapped_workbook_style_params(temp_workspace):
    service = AgentService(planner=InvalidStyleParamsPlanner(), schema_service=FakeSchemaService())

    with pytest.raises(RuntimeError, match="workbook_style.params"):
        await service.plan(
            instruction="生成城市汇总工作簿",
            scope="all",
            file_id=None,
        )
