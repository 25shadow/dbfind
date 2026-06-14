from pydantic import BaseModel, Field


class ExportRequest(BaseModel):
    query_id: str = Field(alias="queryId")
    file_format: str = Field(alias="format")


class ExportResponse(BaseModel):
    export_id: str = Field(alias="exportId")
    file_name: str = Field(alias="fileName")
    download_url: str = Field(alias="downloadUrl")
