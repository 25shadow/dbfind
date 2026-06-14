from pydantic import BaseModel


class SheetResponse(BaseModel):
    id: str
    file_id: str
    name: str
    table_name: str
    row_count: int
    column_count: int
    title: str | None = None
    subtitle: str | None = None
    unit: str | None = None


class SheetPreviewResponse(BaseModel):
    sheet_id: str
    columns: list[str]
    rows: list[dict]
