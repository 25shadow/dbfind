import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import duckdb
import pandas as pd

from app.core.config import get_settings
from app.repositories.file_repository import FileRepository
from app.repositories.sheet_repository import SheetRepository
from app.schemas.agent import (
    AgentExecuteResponse,
    AgentOperationPreview,
    AgentPlan,
    AgentPreviewSheet,
)
from app.schemas.query import QueryRequest
from app.services.duckdb_service import DuckdbService
from app.services.excel_operation_engine import (
    DataFrameOperationEngine,
    WORKBOOK_DESIGN_DEFAULTS,
    WorkbookDesign,
    WorkbookOperationEngine,
)
from app.services.agent_plan_validator import AgentPlanValidationError, AgentPlanValidator
from app.services.query_service import QueryService


class AgentExecutionService:
    def __init__(self) -> None:
        settings = get_settings()
        self.generated_dir = Path(settings.workspace_dir) / "generated"
        self.generated_dir.mkdir(parents=True, exist_ok=True)
        self.file_repository = FileRepository()
        self.sheet_repository = SheetRepository()
        self.duckdb_service = DuckdbService()
        self.query_service = QueryService()
        self.dataframe_engine = DataFrameOperationEngine()
        self.workbook_engine = WorkbookOperationEngine()
        self.plan_validator = AgentPlanValidator()

    def execute(self, *, plan: AgentPlan, file_id: str | None) -> AgentExecuteResponse:
        self._validate_plan(plan)
        if not plan.requires_confirmation:
            raise ValueError("只读查询计划不需要执行 Excel 写入")

        output_id = f"{uuid4().hex}.xlsx"
        output_path = self.generated_dir / output_id
        frames = self._frames_for_plan(plan, file_id)
        if not frames:
            raise ValueError("没有可写出的数据表")

        frames = self._apply_dataframe_steps(frames, plan)
        frames = self._apply_writer_steps(frames, plan)
        design = self._workbook_design_from_plan(plan)
        self.workbook_engine.write_workbook(output_path, frames, design)

        return AgentExecuteResponse(
            status="completed",
            outputId=output_id,
            fileName=f"dbfind-agent-{output_id}",
            downloadUrl=f"/api/agent/generated/{output_id}",
        )

    def preview(self, *, plan: AgentPlan, file_id: str | None) -> AgentOperationPreview:
        self._validate_plan(plan)
        frames, sources = self._frames_and_sources_for_plan(plan, file_id)
        if not frames:
            raise ValueError("没有可预览的数据表")

        frames = self._apply_dataframe_steps(frames, plan)
        frames = self._apply_writer_steps(frames, plan)
        design = self._workbook_design_from_plan(plan)
        sheets = [
            AgentPreviewSheet(
                sheetName=sheet_name,
                columns=[str(column) for column in dataframe.columns],
                rows=dataframe.head(20).where(pd.notnull(dataframe), None).to_dict("records"),
                rowCount=len(dataframe),
            )
            for sheet_name, dataframe in frames
        ]
        affected_columns = sorted({column for sheet in sheets for column in sheet.columns})
        affected_rows = sum(sheet.row_count for sheet in sheets)

        return AgentOperationPreview(
            status="preview",
            affectedRows=affected_rows,
            affectedColumns=affected_columns,
            sheets=sheets,
            sources=sources,
            design={
                "freezeHeader": design.freeze_header,
                "autofilter": design.autofilter,
                "asTable": design.as_table,
                "tableStyle": design.table_style,
                "numberFormats": design.number_formats,
                "conditionalFormats": design.conditional_formats,
                "charts": design.charts,
            },
        )

    def _frames_for_plan(self, plan: AgentPlan, file_id: str | None) -> list[tuple[str, pd.DataFrame]]:
        frames, _sources = self._frames_and_sources_for_plan(plan, file_id)
        return frames

    def _frames_and_sources_for_plan(
        self,
        plan: AgentPlan,
        file_id: str | None,
    ) -> tuple[list[tuple[str, pd.DataFrame]], list[dict]]:
        query_frames, query_sources = self._frames_from_query_steps(plan, file_id)
        if query_frames:
            return query_frames, query_sources

        if plan.scope != "selected":
            raise ValueError("全部文件写入任务需要先通过 query 步骤生成结果表")
        if not file_id:
            raise ValueError("请选择一个已导入的文件")

        data_file = self.file_repository.get_file(file_id)
        if data_file["status"] != "ready":
            raise ValueError("文件尚未完成导入，不能执行 Agent 操作")

        return self._frames_for_file(file_id), []

    def _frames_from_query_steps(
        self,
        plan: AgentPlan,
        file_id: str | None,
    ) -> tuple[list[tuple[str, pd.DataFrame]], list[dict]]:
        frames = []
        sources: list[dict] = []
        for index, step in enumerate(plan.steps, start=1):
            if step.tool != "query":
                continue
            params = self._parse_params(step.params)
            question = params.get("question") or step.purpose or plan.summary
            if not isinstance(question, str) or not question.strip():
                raise ValueError("query 步骤需要 question")
            scope = params.get("scope") or plan.scope
            if scope not in {"selected", "all"}:
                raise ValueError("query 步骤 scope 必须是 selected 或 all")
            response = self.query_service.run(
                QueryRequest(
                    question=question.strip(),
                    scope=scope,
                    fileId=file_id if scope == "selected" else None,
                ),
                record_history=False,
            )
            dataframe = pd.DataFrame(response.rows, columns=response.columns)
            dataframe = self._append_source_context(dataframe, response.sources)
            sources.extend(response.sources)
            sheet_name = params.get("sheetName") or params.get("sheet_name") or f"查询结果{index}"
            frames.append((self.workbook_engine.safe_sheet_name(str(sheet_name)), dataframe))
        return frames, self._dedupe_sources(sources)

    def _append_source_context(self, dataframe: pd.DataFrame, sources: list[dict]) -> pd.DataFrame:
        if dataframe.empty or not sources:
            return dataframe

        source_values = [self._format_source(source) for source in sources]
        source_values = [value for value in source_values if value]
        if not source_values:
            return dataframe

        result = dataframe.copy()
        column_name = self._unique_column_name(result, "来源")
        if len(source_values) == len(result.index):
            result[column_name] = source_values
        elif len(source_values) == 1:
            result[column_name] = source_values[0]
        else:
            result[column_name] = "；".join(dict.fromkeys(source_values))
        return result

    def _format_source(self, source: dict) -> str:
        collection_name = source.get("collectionName") or source.get("collection_name")
        file_name = source.get("fileName") or source.get("file_name")
        sheet_title = source.get("sheetTitle") or source.get("sheet_title")
        sheet_name = source.get("sheetName") or source.get("sheet_name")
        parts = [
            str(value).strip()
            for value in (collection_name, file_name, sheet_title or sheet_name)
            if value is not None and str(value).strip()
        ]
        return " / ".join(parts)

    def _dedupe_sources(self, sources: list[dict]) -> list[dict]:
        unique_sources = []
        seen = set()
        for source in sources:
            key = (
                source.get("fileId") or source.get("file_id"),
                source.get("sheetId") or source.get("sheet_id"),
                source.get("tableName") or source.get("table_name"),
            )
            if key in seen:
                continue
            seen.add(key)
            unique_sources.append(source)
        return unique_sources

    def _unique_column_name(self, dataframe: pd.DataFrame, base_name: str) -> str:
        if base_name not in dataframe.columns:
            return base_name
        index = 2
        while f"{base_name}{index}" in dataframe.columns:
            index += 1
        return f"{base_name}{index}"

    def generated_path(self, output_id: str) -> Path:
        if Path(output_id).name != output_id or Path(output_id).suffix.lower() != ".xlsx":
            raise FileNotFoundError(output_id)
        path = self.generated_dir / output_id
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(output_id)
        return path

    def _frames_for_file(self, file_id: str) -> list[tuple[str, pd.DataFrame]]:
        database_path = self.duckdb_service.database_path_for_file(file_id)
        frames = []
        with duckdb.connect(str(database_path), read_only=True) as conn:
            for sheet in self.sheet_repository.list_sheets(file_id):
                dataframe = conn.execute(
                    f'SELECT * FROM "{sheet["table_name"]}"'
                ).fetchdf()
                dataframe = dataframe.where(pd.notnull(dataframe), None)
                frames.append((sheet["name"], dataframe))
        return frames

    def _apply_dataframe_steps(
        self, frames: list[tuple[str, pd.DataFrame]], plan: AgentPlan
    ) -> list[tuple[str, pd.DataFrame]]:
        operations: list[dict[str, Any]] = []
        for step in plan.steps:
            if step.tool != "dataframe_transform":
                continue
            params = self._parse_params(step.params)
            step_operations = params.get("operations", [])
            if not isinstance(step_operations, list):
                raise ValueError("dataframe_transform.params.operations 必须是数组")
            operations.extend(step_operations)

        if not operations:
            return frames
        return [
            (sheet_name, self.dataframe_engine.apply(dataframe, operations))
            for sheet_name, dataframe in frames
        ]

    def _apply_writer_steps(
        self, frames: list[tuple[str, pd.DataFrame]], plan: AgentPlan
    ) -> list[tuple[str, pd.DataFrame]]:
        sheet_name: str | None = None
        for step in plan.steps:
            if step.tool != "workbook_writer":
                continue
            params = self._parse_params(step.params)
            candidate = params.get("sheetName") or params.get("sheet_name")
            if isinstance(candidate, str) and candidate.strip():
                sheet_name = candidate.strip()

        if not sheet_name or len(frames) != 1:
            return frames
        return [(self.workbook_engine.safe_sheet_name(sheet_name), frames[0][1])]

    def _workbook_design_from_plan(self, plan: AgentPlan) -> WorkbookDesign:
        number_formats: dict[str, str] = {}
        header_fill = WORKBOOK_DESIGN_DEFAULTS.header_fill
        freeze_header = WORKBOOK_DESIGN_DEFAULTS.freeze_header
        autofilter = WORKBOOK_DESIGN_DEFAULTS.autofilter
        as_table = WORKBOOK_DESIGN_DEFAULTS.as_table
        table_style = WORKBOOK_DESIGN_DEFAULTS.table_style
        conditional_formats: list[dict[str, Any]] = []
        charts: list[dict[str, Any]] = []
        for step in plan.steps:
            if step.tool != "workbook_style":
                continue
            params = self._parse_params(step.params)
            candidate_formats = params.get("numberFormats") or params.get("number_formats")
            if isinstance(candidate_formats, dict):
                number_formats.update(
                    {
                        str(column): str(number_format)
                        for column, number_format in candidate_formats.items()
                    }
                )
            if isinstance(params.get("headerFill"), str):
                header_fill = params["headerFill"]
            if isinstance(params.get("freezeHeader"), bool):
                freeze_header = params["freezeHeader"]
            if isinstance(params.get("autofilter"), bool):
                autofilter = params["autofilter"]
            if isinstance(params.get("asTable"), bool):
                as_table = params["asTable"]
            if isinstance(params.get("as_table"), bool):
                as_table = params["as_table"]
            if isinstance(params.get("tableStyle"), str):
                table_style = params["tableStyle"]
            if isinstance(params.get("table_style"), str):
                table_style = params["table_style"]
            candidate_conditional_formats = (
                params.get("conditionalFormats") or params.get("conditional_formats")
            )
            if isinstance(candidate_conditional_formats, list):
                conditional_formats.extend(
                    item for item in candidate_conditional_formats if isinstance(item, dict)
                )
            candidate_charts = params.get("charts")
            if isinstance(candidate_charts, list):
                charts.extend(item for item in candidate_charts if isinstance(item, dict))
        return WorkbookDesign(
            freeze_header=freeze_header,
            autofilter=autofilter,
            header_fill=header_fill,
            number_formats=number_formats,
            as_table=as_table,
            table_style=table_style,
            conditional_formats=conditional_formats,
            charts=charts,
        )

    def _parse_params(self, params: str) -> dict[str, Any]:
        if not params:
            return {}
        try:
            parsed = json.loads(params)
        except json.JSONDecodeError as exc:
            raise ValueError("Agent 步骤参数不是合法 JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("Agent 步骤参数必须是 JSON 对象")
        return parsed

    def _validate_plan(self, plan: AgentPlan) -> None:
        try:
            self.plan_validator.validate(plan)
        except AgentPlanValidationError as exc:
            raise ValueError(str(exc)) from exc
