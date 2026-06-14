from pydantic import BaseModel, ConfigDict, Field


class CollectionCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    parent_id: str | None = Field(default=None, alias="parentId")


class CollectionUpdateRequest(BaseModel):
    name: str = Field(min_length=1)
    parent_id: str | None = Field(default=None, alias="parentId")


class CollectionMoveRequest(BaseModel):
    parent_id: str | None = Field(default=None, alias="parentId")


class BulkMoveRequest(BaseModel):
    collection_ids: list[str] = Field(default_factory=list, alias="collectionIds")
    file_ids: list[str] = Field(default_factory=list, alias="fileIds")
    target_collection_id: str | None = Field(default=None, alias="targetCollectionId")


class CollectionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    source_region: str | None = Field(default=None, alias="sourceRegion")
    source_year: int | None = Field(default=None, alias="sourceYear")
    source_type: str | None = Field(default=None, alias="sourceType")
    source_scope: str | None = Field(default=None, alias="sourceScope")
    parent_id: str | None = Field(default=None, alias="parentId")
    file_count: int = Field(default=0, alias="fileCount")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
