from __future__ import annotations

from typing import Protocol

from pydantic import ValidationError

from app.schemas.agent import AgentPlan
from app.services.agent_tools import create_excel_agent_tools
from app.services.settings_service import SettingsService


class AgentPlanner(Protocol):
    async def plan(
        self,
        instruction: str,
        scope: str,
        file_id: str | None,
        schema_context: str = "",
    ) -> AgentPlan | None:
        ...


class OpenAIAgentsPlanner:
    """OpenAI Agents SDK planner for Excel Agent tasks.

    The planner returns structured `AgentPlan` output. If the SDK is unavailable,
    the model is not configured, or the provider fails to produce valid output,
    callers must surface the failure instead of substituting local rules.
    """

    async def plan(
        self,
        instruction: str,
        scope: str,
        file_id: str | None,
        schema_context: str = "",
    ) -> AgentPlan | None:
        settings = SettingsService().get()
        if not settings.api_key:
            raise RuntimeError("OpenAI Agents SDK 需要先配置 API Key")

        try:
            from agents import (
                Agent,
                AsyncOpenAI,
                OpenAIChatCompletionsModel,
                Runner,
                set_default_openai_api,
                set_default_openai_client,
            )
        except Exception as exc:
            raise RuntimeError(f"OpenAI Agents SDK 不可用: {exc}") from exc

        try:
            base_url = self._sdk_base_url(settings.ai_base_url, settings.ai_chat_path)
            client = AsyncOpenAI(api_key=settings.api_key, base_url=base_url)
            set_default_openai_client(client, use_for_tracing=False)
            set_default_openai_api("chat_completions")
            model = OpenAIChatCompletionsModel(model=settings.model, openai_client=client)

            agent = Agent(
                name="DbFind Excel Agent Planner",
                model=model,
                instructions=self._instructions(),
                tools=create_excel_agent_tools(),
                output_type=AgentPlan,
            )
            result = await Runner.run(
                agent,
                input=self._input(instruction, scope, file_id, schema_context),
                max_turns=4,
            )
        except Exception as exc:
            raise RuntimeError(f"OpenAI Agents SDK 执行失败: {exc}") from exc

        return self._coerce_plan(result.final_output)

    def _coerce_plan(self, value) -> AgentPlan | None:
        if isinstance(value, AgentPlan):
            return value
        if isinstance(value, str):
            try:
                return AgentPlan.model_validate_json(value)
            except (ValidationError, ValueError) as exc:
                raise RuntimeError(f"OpenAI Agents SDK 返回的结构化计划不合法: {exc}") from exc
        if isinstance(value, dict):
            try:
                return AgentPlan.model_validate(value)
            except ValidationError as exc:
                raise RuntimeError(f"OpenAI Agents SDK 返回的结构化计划不合法: {exc}") from exc
        raise RuntimeError("OpenAI Agents SDK 没有返回可解析的 Excel Agent 计划")

    def _sdk_base_url(self, ai_base_url: str, ai_chat_path: str) -> str:
        base = ai_base_url.rstrip("/")
        if ai_chat_path.startswith("/v1/") and not base.endswith("/v1"):
            return f"{base}/v1"
        return base

    def _input(
        self,
        instruction: str,
        scope: str,
        file_id: str | None,
        schema_context: str = "",
    ) -> str:
        target = file_id or "全部已导入文件"
        schema_text = schema_context.strip() or "当前没有可用 Schema。"
        return (
            f"用户任务：{instruction}\n"
            f"Agent 范围：{scope}\n"
            f"目标文件：{target}\n"
            "可用 Schema：\n"
            f"{schema_text}\n"
            "字段约束：必须优先使用可用 Schema 中出现的真实表名和字段名；"
            "不要使用上下文中不存在的字段。"
            "请根据用户任务生成 AgentPlan。"
        )

    def _instructions(self) -> str:
        return (
            "你是 DbFind 的 Excel Agent 规划器。你只生成结构化计划，不声称已经执行。"
            "必须把用户自然语言映射为通用 Excel 操控能力，而不是匹配固定例句。"
            "不能编造字段、表名、Sheet 或统计结果；如果任务需要字段，必须来自输入里的可用 Schema。"
            "如果用户说了一个不存在的字段名，要改用可用 Schema 中最接近的真实字段，"
            "或让 query 步骤通过 Text2SQL 从真实字段生成结果列。"
            "dataframe_transform、workbook_writer、workbook_style 只能引用 query 结果列或 Schema 中存在的字段。"
            "可用工具只有 query_excel_data、transform_dataframe、write_workbook、style_workbook。"
            "最终 AgentPlan.steps.tool 必须映射为 query、dataframe_transform、workbook_writer、workbook_style。"
            "只要用户是在询问、检索、统计、比较、筛选、排序、汇总或查看 Excel 数据，"
            "就规划为只读查询任务，不要要求用户再解释要做什么。"
            "查询类任务 intent=query，requiresConfirmation=false，riskLevel=low，steps 只包含 query。"
            "如果用户要求生成计算表、生成表格、生成工作簿、导出新表、写入、格式修改、清洗、合并或设计，"
            "必须规划为 excel_operation，不要只输出查询解释。"
            "如果生成表格需要先查询或汇总数据，steps 必须先包含 query，再把查询结果交给 "
            "dataframe_transform、workbook_writer 和 workbook_style。"
            "写入、格式修改、清洗、合并、生成、设计类任务 intent=excel_operation，"
            "requiresConfirmation=true，riskLevel=medium，必须先预览再执行。"
            "dataframe_transform.params 必须是 JSON 对象，形如 {\"operations\": [...]}。"
            "所有 step.params 必须是实际 JSON 对象；params 不能是占位字符串，"
            "不能写成 question、operations、styles、output_mode 这类词。"
            "最终 AgentPlan 里的 step.params 也不能直接复制 function tool 返回的包装字段。"
            "query.params 必须包含 question 和 scope；workbook_writer.params 可包含 sheetName；"
            "workbook_style.params 可包含 asTable、tableStyle、numberFormats、conditionalFormats、charts。"
            "可执行 operations 必须是成熟库驱动的通用操作，不允许为固定案例或特定对象设计专用操作。"
            "当前已接入的 operations："
            "filter_in({type,column,values})、select_columns({type,columns})、"
            "sort_values({type,by,ascending})、round({type,columns,decimals})、"
            "eval_expression({type,expression})、query({type,expression})、"
            "rename_columns({type,columns})、drop_duplicates({type,subset,keep})、"
            "dropna({type,subset,how})、fillna({type,values})、astype({type,columns})、"
            "groupby_agg({type,by,aggregations})。"
            "eval_expression 使用 pandas DataFrame.eval 语法，query 使用 pandas DataFrame.query 语法。"
            "分组、汇总、跨行比较、两个对象相差多少等任务优先在 query/Text2SQL 中生成结果列，"
            "不要规划自定义语义操作。"
            "workbook_writer.params 使用 sheetName 指定单 Sheet 输出名称。"
            "workbook_style.params 使用 numberFormats 指定列名到 Excel 数字格式的映射，"
            "也可以使用 asTable、tableStyle、"
            "conditionalFormats、charts 生成 Excel Table、条件格式和图表。"
            "默认不覆盖原始文件，只生成新 Sheet 或新工作簿。"
            "scope 必须沿用输入 scope。"
            "status 使用 planned。"
            "服务端已经保证用户任务非空，所以不要输出用户输入为空或需要更多信息。"
        )
