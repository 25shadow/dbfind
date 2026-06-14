import json
from typing import Any

from app.schemas.agent import AgentPlan
from app.services.agent_runtime import AgentPlanner, OpenAIAgentsPlanner
from app.services.schema_service import SchemaService


class AgentService:
    def __init__(
        self,
        planner: AgentPlanner | None = None,
        schema_service: SchemaService | None = None,
    ) -> None:
        self.planner = planner or OpenAIAgentsPlanner()
        self.schema_service = schema_service or SchemaService()

    async def plan(self, instruction: str, scope: str, file_id: str | None) -> AgentPlan:
        normalized_scope = scope.lower().strip()
        if normalized_scope not in {"selected", "all"}:
            raise ValueError("Agent 范围必须是 selected 或 all")
        if normalized_scope == "selected" and not file_id:
            raise ValueError("请选择一个已导入的文件")

        text = instruction.strip()
        if not text:
            raise ValueError("请输入要让 Excel Agent 执行的任务")

        fast_plan = self._fast_plan(text, normalized_scope)
        if fast_plan:
            self._validate_plan_params(fast_plan)
            return fast_plan

        schema_context = self._schema_context(text, normalized_scope, file_id)
        sdk_plan = await self.planner.plan(text, normalized_scope, file_id, schema_context)
        if sdk_plan:
            self._validate_plan_params(sdk_plan)
            return sdk_plan

        raise RuntimeError("OpenAI Agents SDK 未能生成有效的 Excel Agent 计划")

    def _schema_context(self, instruction: str, scope: str, file_id: str | None) -> str:
        if scope == "selected":
            return self.schema_service.build_schema_text(file_id or "")
        return self.schema_service.build_relevant_all_files_schema_text(instruction)

    def _fast_plan(self, instruction: str, scope: str) -> AgentPlan | None:
        if not self._is_common_workbook_generation(instruction):
            return None

        sheet_name = "Agent结果"
        return AgentPlan(
            intent="excel_operation",
            scope=scope,
            summary=f"查询数据并生成 Excel 工作簿：{instruction}",
            requiresConfirmation=True,
            riskLevel="medium",
            steps=[
                {
                    "tool": "query",
                    "purpose": "根据用户任务查询并生成结果表",
                    "params": {
                        "question": instruction,
                        "scope": scope,
                        "sheetName": sheet_name,
                    },
                },
                {
                    "tool": "workbook_writer",
                    "purpose": "把查询结果写入新的 Excel 工作簿",
                    "params": {"sheetName": sheet_name},
                },
                {
                    "tool": "workbook_style",
                    "purpose": "应用通用表格样式，便于筛选和阅读",
                    "params": {
                        "freezeHeader": True,
                        "autofilter": True,
                        "asTable": True,
                    },
                },
            ],
            preview={},
            status="planned",
        )

    def _is_common_workbook_generation(self, instruction: str) -> bool:
        generation_terms = ("生成", "导出", "做一张", "做一个", "新建", "创建", "保存")
        output_terms = ("表格", "工作簿", "Excel", "excel", "xlsx", "报表", "结果表", "表")
        comparison_terms = ("对比", "比较", "相差", "差值", "减法", "差多少")
        return any(term in instruction for term in generation_terms) and any(
            term in instruction for term in output_terms
        ) and any(term in instruction for term in comparison_terms)

    def _validate_plan_params(self, plan: AgentPlan) -> None:
        for step in plan.steps:
            params = self._parse_params(step.params)
            if step.tool == "query":
                self._validate_query_params(params)
            elif step.tool == "dataframe_transform":
                self._validate_dataframe_params(params)
            elif step.tool == "workbook_writer":
                self._validate_workbook_writer_params(params)
            elif step.tool == "workbook_style":
                self._validate_workbook_style_params(params)

    def _parse_params(self, params: str) -> dict[str, Any]:
        if not params:
            return {}
        parsed = json.loads(params)
        if not isinstance(parsed, dict):
            raise RuntimeError("Agent 计划 params 必须是 JSON 对象")
        return parsed

    def _validate_query_params(self, params: dict[str, Any]) -> None:
        question = params.get("question")
        scope = params.get("scope")
        if not isinstance(question, str) or not question.strip():
            raise RuntimeError("query.params 必须包含 question")
        if scope is not None and scope not in {"selected", "all"}:
            raise RuntimeError("query.params.scope 必须是 selected 或 all")

    def _validate_dataframe_params(self, params: dict[str, Any]) -> None:
        operations = params.get("operations")
        if not isinstance(operations, list):
            raise RuntimeError("dataframe_transform.params.operations 必须是数组")
        for operation in operations:
            if not isinstance(operation, dict):
                raise RuntimeError("dataframe_transform operation 必须是 JSON 对象")
            operation_type = operation.get("type")
            if operation_type == "groupby_agg":
                if not isinstance(operation.get("aggregations"), dict):
                    raise RuntimeError("groupby_agg.aggregations 必须是对象")
                by = operation.get("by")
                if not isinstance(by, (str, list)):
                    raise RuntimeError("groupby_agg.by 必须是字段名或字段数组")
            elif operation_type in {"filter_in", "query", "eval_expression", "select_columns", "sort_values", "round", "rename_columns", "drop_duplicates", "dropna", "fillna", "astype"}:
                continue
            else:
                raise RuntimeError(f"不支持的 dataframe_transform operation: {operation_type}")

    def _validate_workbook_writer_params(self, params: dict[str, Any]) -> None:
        sheet_name = params.get("sheetName") or params.get("sheet_name")
        if sheet_name is not None and not isinstance(sheet_name, str):
            raise RuntimeError("workbook_writer.params.sheetName 必须是字符串")

    def _validate_workbook_style_params(self, params: dict[str, Any]) -> None:
        if "styles" in params:
            raise RuntimeError("workbook_style.params 不能使用 styles 包装字段")
        number_formats = params.get("numberFormats") or params.get("number_formats")
        if number_formats is not None and not isinstance(number_formats, dict):
            raise RuntimeError("workbook_style.params.numberFormats 必须是对象")
        conditional_formats = params.get("conditionalFormats") or params.get("conditional_formats")
        if conditional_formats is not None and not isinstance(conditional_formats, list):
            raise RuntimeError("workbook_style.params.conditionalFormats 必须是数组")
        charts = params.get("charts")
        if charts is not None and not isinstance(charts, list):
            raise RuntimeError("workbook_style.params.charts 必须是数组")
