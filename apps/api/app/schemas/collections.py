from pydantic import BaseModel, ConfigDict, Field
from typing import Any


class CollectionCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    parent_id: str | None = Field(default=None, alias="parentId")


class CollectionUpdateRequest(BaseModel):
    name: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    parent_id: str | None = Field(default=None, alias="parentId")


class CollectionMoveRequest(BaseModel):
    parent_id: str | None = Field(default=None, alias="parentId")


class CollectionMetadataSuggestionRequest(BaseModel):
    name: str = Field(min_length=1)


class CollectionMetadataSuggestionResponse(BaseModel):
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class BulkMoveRequest(BaseModel):
    collection_ids: list[str] = Field(default_factory=list, alias="collectionIds")
    file_ids: list[str] = Field(default_factory=list, alias="fileIds")
    target_collection_id: str | None = Field(default=None, alias="targetCollectionId")


class CollectionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    parent_id: str | None = Field(default=None, alias="parentId")
    file_count: int = Field(default=0, alias="fileCount")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
