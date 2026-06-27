import pytest

from app.schemas.agent import AgentPlan, AgentPreview, AgentStep
from app.services.agent_plan_validator import AgentPlanValidationError, AgentPlanValidator


def _plan_with_step(step: AgentStep) -> AgentPlan:
    return AgentPlan(
        intent="excel_operation",
        scope="selected",
        summary="生成工作簿",
        requiresConfirmation=True,
        riskLevel="medium",
        steps=[step],
        preview=AgentPreview(),
    )


def test_agent_plan_validator_allows_known_dataframe_operations():
    plan = _plan_with_step(
        AgentStep(
            tool="dataframe_transform",
            purpose="筛选并排序",
            params={
                "operations": [
                    {"type": "filter_in", "column": "城市", "values": ["广州"]},
                    {"type": "query", "expression": "`金额` >= 8"},
                    {"type": "round", "columns": ["金额"], "decimals": 1},
                ]
            },
        )
    )

    AgentPlanValidator().validate(plan)


def test_agent_plan_validator_allows_simple_eval_expression():
    plan = _plan_with_step(
        AgentStep(
            tool="dataframe_transform",
            purpose="计算利润",
            params={
                "operations": [
                    {"type": "eval_expression", "expression": "`利润` = `收入` - `成本` * 0.8"}
                ]
            },
        )
    )

    AgentPlanValidator().validate(plan)


def test_agent_plan_validator_rejects_unknown_dataframe_operation():
    plan = _plan_with_step(
        AgentStep(
            tool="dataframe_transform",
            purpose="执行未知动作",
            params={"operations": [{"type": "run_python", "code": "print(1)"}]},
        )
    )

    with pytest.raises(AgentPlanValidationError, match="不支持的 dataframe_transform operation"):
        AgentPlanValidator().validate(plan)


def test_agent_plan_validator_rejects_dangerous_dataframe_expression():
    plan = _plan_with_step(
        AgentStep(
            tool="dataframe_transform",
            purpose="危险表达式",
            params={
                "operations": [
                    {
                        "type": "query",
                        "expression": "__import__('os').system('touch /tmp/dbfind-owned')",
                    }
                ]
            },
        )
    )

    with pytest.raises(AgentPlanValidationError, match="表达式包含不允许的内容"):
        AgentPlanValidator().validate(plan)


@pytest.mark.parametrize(
    "expression",
    [
        "abs(`金额`) > 8",
        "`金额`.to_string() == '8'",
        "`金额`[0] > 8",
        "@external_value > 8",
    ],
)
def test_agent_plan_validator_rejects_expressions_outside_safe_subset(expression):
    plan = _plan_with_step(
        AgentStep(
            tool="dataframe_transform",
            purpose="越界表达式",
            params={"operations": [{"type": "query", "expression": expression}]},
        )
    )

    with pytest.raises(AgentPlanValidationError, match="表达式超出安全语法"):
        AgentPlanValidator().validate(plan)


def test_agent_plan_validator_rejects_writer_file_paths():
    plan = _plan_with_step(
        AgentStep(
            tool="workbook_writer",
            purpose="写入指定路径",
            params={"outputPath": "/tmp/out.xlsx"},
        )
    )

    with pytest.raises(AgentPlanValidationError, match="不能指定文件路径"):
        AgentPlanValidator().validate(plan)
