from pydantic import BaseModel, ConfigDict, Field

from app.schemas.files import FileResponse


class UploadSessionCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    file_name: str = Field(alias="fileName")
    file_size: int = Field(alias="fileSize", gt=0)
    chunk_size: int = Field(default=2 * 1024 * 1024, alias="chunkSize", gt=0)
    collection_id: str | None = Field(default=None, alias="collectionId")


class UploadSessionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    file_name: str = Field(alias="fileName")
    file_size: int = Field(alias="fileSize")
    chunk_size: int = Field(alias="chunkSize")
    total_chunks: int = Field(alias="totalChunks")
    collection_id: str | None = Field(default=None, alias="collectionId")
    status: str
    uploaded_chunks: list[int] = Field(alias="uploadedChunks")
    uploaded_bytes: int = Field(alias="uploadedBytes")
    file_id: str | None = Field(default=None, alias="fileId")
    error: str | None = None
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    file: FileResponse | None = None
