import json
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AgentRequest(BaseModel):
    instruction: str
    scope: str = "selected"
    file_id: str | None = Field(default=None, alias="fileId")


class AgentStep(BaseModel):
    tool: Literal["query", "dataframe_transform", "workbook_writer", "workbook_style"]
    purpose: str
    params: str = ""

    @field_validator("params", mode="before")
    @classmethod
    def serialize_params(cls, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            if value.strip():
                try:
                    parsed = json.loads(value)
                except json.JSONDecodeError as exc:
                    raise ValueError("params 必须是 JSON 对象字符串，不能是占位字符串") from exc
                if not isinstance(parsed, dict):
                    raise ValueError("params 必须是 JSON 对象字符串")
            return value
        if not isinstance(value, dict):
            raise ValueError("params 必须是 JSON 对象")
        return json.dumps(value, ensure_ascii=False)


class AgentPreview(BaseModel):
    affected_rows: int | None = Field(default=None, alias="affectedRows")
    affected_columns: list[str] = Field(default_factory=list, alias="affectedColumns")
    sample_before_after: list[str] = Field(default_factory=list, alias="sampleBeforeAfter")


class AgentPlan(BaseModel):
    intent: Literal["query", "excel_operation"]
    scope: Literal["selected", "all"]
    summary: str
    requires_confirmation: bool = Field(alias="requiresConfirmation")
    risk_level: Literal["low", "medium", "high"] = Field(alias="riskLevel")
    steps: list[AgentStep] = Field(min_length=1)
    preview: AgentPreview = Field(default_factory=AgentPreview)
    status: Literal["draft", "planned"] = "draft"


class AgentTaskResponse(BaseModel):
    task_id: str | None = Field(default=None, alias="taskId")
    plan: AgentPlan


class AgentExecuteRequest(BaseModel):
    task_id: str | None = Field(default=None, alias="taskId")
    file_id: str | None = Field(default=None, alias="fileId")
    plan: AgentPlan


class AgentExecuteResponse(BaseModel):
    status: str
    output_id: str = Field(alias="outputId")
    file_name: str = Field(alias="fileName")
    download_url: str = Field(alias="downloadUrl")


class AgentPreviewRequest(BaseModel):
    task_id: str | None = Field(default=None, alias="taskId")
    file_id: str | None = Field(default=None, alias="fileId")
    plan: AgentPlan


class AgentPreviewSheet(BaseModel):
    sheet_name: str = Field(alias="sheetName")
    columns: list[str]
    rows: list[dict]
    row_count: int = Field(alias="rowCount")


class AgentOperationPreview(BaseModel):
    status: Literal["preview"]
    affected_rows: int = Field(alias="affectedRows")
    affected_columns: list[str] = Field(alias="affectedColumns")
    sheets: list[AgentPreviewSheet]
    sources: list[dict] = Field(default_factory=list)
    design: dict = Field(default_factory=dict)


class AgentTaskLog(BaseModel):
    timestamp: str
    stage: str
    status: str
    message: str


class AgentTaskItem(BaseModel):
    id: str
    instruction: str
    scope: str
    file_id: str | None = Field(default=None, alias="fileId")
    plan: AgentPlan
    status: str
    output_id: str | None = Field(default=None, alias="outputId")
    download_url: str | None = Field(default=None, alias="downloadUrl")
    error: str | None = None
    query_result: dict | None = Field(default=None, alias="queryResult")
    preview_result: AgentOperationPreview | None = Field(default=None, alias="previewResult")
    sources: list[dict] = Field(default_factory=list)
    logs: list[AgentTaskLog] = Field(default_factory=list)
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class AgentTaskListResponse(BaseModel):
    tasks: list[AgentTaskItem]
