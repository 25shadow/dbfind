import pytest

from app.schemas.agent import AgentPlan, AgentStep
from app.services.agent_runtime import OpenAIAgentsPlanner


def test_agent_plan_schema_is_valid_for_openai_agents_strict_output():
    from agents import AgentOutputSchema

    schema = AgentOutputSchema(AgentPlan)

    assert schema.json_schema()["type"] == "object"


def test_agent_step_rejects_placeholder_params_string():
    with pytest.raises(ValueError, match="params"):
        AgentStep(tool="query", purpose="查询数据", params="question")


def test_openai_agents_planner_instructions_include_operation_contracts():
    instructions = OpenAIAgentsPlanner()._instructions()

    assert "filter_in" in instructions
    assert "select_columns" in instructions
    assert "sort_values" in instructions
    assert "round" in instructions
    assert "eval_expression" in instructions
    assert "rename_columns" in instructions
    assert "drop_duplicates" in instructions
    assert "groupby_agg" in instructions
    assert "pandas DataFrame.eval" in instructions
    assert "pandas DataFrame.query" in instructions
    assert "sheetName" in instructions
    assert "numberFormats" in instructions
    assert "charts" in instructions
    assert "add_difference_column" not in instructions
    assert "params 不能是占位字符串" in instructions


def test_openai_agents_planner_instructions_route_generated_tables_to_operations():
    instructions = OpenAIAgentsPlanner()._instructions()

    assert "生成计算表" in instructions
    assert "excel_operation" in instructions
    assert "不要只输出查询解释" in instructions
    assert "先包含 query" in instructions


def test_openai_agents_planner_input_includes_schema_context():
    planner = OpenAIAgentsPlanner()

    prompt = planner._input(
        "生成按城市汇总的工作簿",
        "all",
        None,
        'CREATE TABLE "t" ("城市" VARCHAR, "街道数量" DOUBLE);',
    )

    assert "可用 Schema" in prompt
    assert '"街道数量"' in prompt
    assert "不要使用上下文中不存在的字段" in prompt


def test_openai_agents_planner_instructions_forbid_unknown_columns():
    instructions = OpenAIAgentsPlanner()._instructions()

    assert "不能编造字段" in instructions
    assert "不存在的字段" in instructions


@pytest.mark.anyio
async def test_openai_agents_planner_surfaces_sdk_errors(monkeypatch):
    class Settings:
        api_key = "test-key"
        ai_base_url = "https://example.test"
        ai_chat_path = "/v1/chat/completions"
        model = "test-model"

    async def fail_run(*args, **kwargs):
        raise RuntimeError("provider rejected structured output")

    monkeypatch.setattr("app.services.agent_runtime.SettingsService.get", lambda self: Settings())
    monkeypatch.setattr("agents.Runner.run", fail_run)

    with pytest.raises(RuntimeError, match="provider rejected structured output"):
        await OpenAIAgentsPlanner().plan("查询数据", "all", None)


@pytest.mark.anyio
async def test_openai_agents_planner_binds_openai_compatible_chat_model(monkeypatch):
    from agents import OpenAIChatCompletionsModel

    class Settings:
        api_key = "test-key"
        ai_base_url = "https://example.test"
        ai_chat_path = "/v1/chat/completions"
        model = "deepseek-ai/DeepSeek-V4-Flash"

    class Result:
        final_output = AgentPlan(
            intent="query",
            scope="all",
            summary="查询广东省各年的乡村户数",
            requiresConfirmation=False,
            riskLevel="low",
            steps=[AgentStep(tool="query", purpose="查询广东省各年的乡村户数")],
        )

    captured = {}

    async def capture_run(agent, *args, **kwargs):
        captured["model"] = agent.model
        return Result()

    monkeypatch.setattr("app.services.agent_runtime.SettingsService.get", lambda self: Settings())
    monkeypatch.setattr("agents.Runner.run", capture_run)

    await OpenAIAgentsPlanner().plan("帮我查一下广东省各年的乡村户数有多少", "all", None)

    assert isinstance(captured["model"], OpenAIChatCompletionsModel)
