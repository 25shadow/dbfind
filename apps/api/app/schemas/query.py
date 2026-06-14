from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    file_id: str | None = Field(default=None, alias="fileId")
    question: str
    scope: str = "selected"


class QueryResponse(BaseModel):
    query_id: str = Field(alias="queryId")
    file_id: str = Field(alias="fileId")
    scope: str
    question: str
    sql: str
    columns: list[str]
    rows: list[dict]
    explanation: str
    created_at: str = Field(alias="createdAt")
    initial_sql: str | None = Field(default=None, alias="initialSql")
    repair_error: str | None = Field(default=None, alias="repairError")
    repaired_sql: str | None = Field(default=None, alias="repairedSql")
    was_repaired: bool = Field(default=False, alias="wasRepaired")
    sources: list[dict] = Field(default_factory=list)
