from pydantic import BaseModel, ConfigDict, Field

from app.schemas.table_structure import TableStructurePlan


class FileResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    status: str = Field(pattern="^(uploaded|importing|ready|needs_review|failed)$")
    collection_id: str | None = Field(default=None, alias="collectionId")
    collection_name: str | None = Field(default=None, alias="collectionName")
    created_at: str = Field(alias="createdAt")


class BulkUploadItemResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    file_name: str = Field(alias="fileName")
    success: bool
    file: FileResponse | None = None
    error: str | None = None


class BulkUploadSummaryResponse(BaseModel):
    total: int
    success: int
    failed: int


class BulkUploadResponse(BaseModel):
    summary: BulkUploadSummaryResponse
    results: list[BulkUploadItemResponse]


class RawContentBlockResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    region: str
    text: str
    cells: list[str]


class StructurePreviewItemResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sheet_name: str = Field(alias="sheetName")
    block_region: str | None = Field(alias="blockRegion")
    status: str = Field(pattern="^(ready|needs_review)$")
    issues: list[str]
    quality_confidence: str = Field(alias="qualityConfidence")
    title: str | None = None
    subtitle: str | None = None
    unit: str | None = None
    plan: TableStructurePlan | None = None
    columns: list[str]
    preview_rows: list[dict] = Field(alias="previewRows")
    source_cell_map: dict[str, list[str]] = Field(alias="sourceCellMap")
    raw_content_blocks: list[RawContentBlockResponse] = Field(
        default_factory=list,
        alias="rawContentBlocks",
    )


class StructurePreviewResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    file_id: str = Field(alias="fileId")
    items: list[StructurePreviewItemResponse]


class StructureCommitItemRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sheet_name: str = Field(alias="sheetName")
    plan: TableStructurePlan


class StructureCommitRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[StructureCommitItemRequest]
