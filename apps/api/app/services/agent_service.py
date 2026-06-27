from app.schemas.agent import AgentPlan
from app.services.agent_plan_validator import AgentPlanValidator
from app.services.agent_runtime import AgentPlanner, OpenAIAgentsPlanner
from app.services.agent_router import AgentRouter
from app.services.schema_service import SchemaService


class AgentService:
    def __init__(
        self,
        planner: AgentPlanner | None = None,
        schema_service: SchemaService | None = None,
        validator: AgentPlanValidator | None = None,
        router: AgentRouter | None = None,
    ) -> None:
        self.planner = planner or OpenAIAgentsPlanner()
        self.schema_service = schema_service or SchemaService()
        self.validator = validator or AgentPlanValidator()
        self.router = router or AgentRouter()

    async def plan(self, instruction: str, scope: str, file_id: str | None) -> AgentPlan:
        normalized_scope = scope.lower().strip()
        if normalized_scope not in {"selected", "all"}:
            raise ValueError("Agent 范围必须是 selected 或 all")
        if normalized_scope == "selected" and not file_id:
            raise ValueError("请选择一个已导入的文件")

        text = instruction.strip()
        if not text:
            raise ValueError("请输入要让 Excel Agent 执行的任务")

        route = self.router.route(text)
        if route.kind == "query_only":
            return self._query_plan(text, normalized_scope)
        if route.kind == "report_generation":
            report_plan = self._report_generation_plan(text, normalized_scope)
            self.validator.validate(report_plan)
            return report_plan

        schema_context = self._schema_context(text, normalized_scope, file_id)
        sdk_plan = await self.planner.plan(text, normalized_scope, file_id, schema_context)
        if sdk_plan:
            self.validator.validate(sdk_plan)
            return sdk_plan

        raise RuntimeError("OpenAI Agents SDK 未能生成有效的 Excel Agent 计划")

    def _schema_context(self, instruction: str, scope: str, file_id: str | None) -> str:
        if scope == "selected":
            return self.schema_service.build_schema_text(file_id or "")
        return self.schema_service.build_relevant_all_files_schema_text(instruction)

    def _query_plan(self, instruction: str, scope: str) -> AgentPlan:
        return AgentPlan(
            intent="query",
            scope=scope,
            summary=f"查询数据：{instruction}",
            requiresConfirmation=False,
            riskLevel="low",
            steps=[
                {
                    "tool": "query",
                    "purpose": "根据用户问题查询数据",
                    "params": {
                        "question": instruction,
                        "scope": scope,
                    },
                },
            ],
            preview={},
            status="planned",
        )

    def _report_generation_plan(self, instruction: str, scope: str) -> AgentPlan:
        sheet_name = self._report_sheet_name(instruction)
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

    def _report_sheet_name(self, instruction: str) -> str:
        text = instruction.strip()
        for prefix in ("请", "帮我", "帮忙", "给我"):
            text = text.removeprefix(prefix).strip()
        for phrase in ("生成一张", "生成一个", "生成", "导出一张", "导出一个", "导出", "做一张", "做一个"):
            text = text.replace(phrase, "", 1).strip()
        for suffix in ("给我", "谢谢"):
            text = text.removesuffix(suffix).strip()
        safe = "".join("_" if char in r'[]:*?/\\' else char for char in text).strip(" _")
        return (safe or "查询结果")[:31]
