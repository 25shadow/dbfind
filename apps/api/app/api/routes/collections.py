from fastapi import APIRouter, UploadFile
from starlette.status import HTTP_204_NO_CONTENT

from app.schemas.collections import (
    BulkMoveRequest,
    CollectionCreateRequest,
    CollectionMoveRequest,
    CollectionResponse,
    CollectionUpdateRequest,
)
from app.schemas.files import FileResponse
from app.services.collection_service import CollectionService
from app.services.file_service import FileService

router = APIRouter()


@router.get("", response_model=list[CollectionResponse])
async def list_collections(parent_id: str | None = None) -> list[CollectionResponse]:
    return CollectionService().list_children(parent_id)


@router.get("/all", response_model=list[CollectionResponse])
async def list_all_collections() -> list[CollectionResponse]:
    return CollectionService().list()


@router.post("", response_model=CollectionResponse)
async def create_collection(payload: CollectionCreateRequest) -> CollectionResponse:
    return CollectionService().create(payload.name, payload.parent_id)


@router.get("/{collection_id}", response_model=CollectionResponse)
async def get_collection(collection_id: str) -> CollectionResponse:
    return CollectionService().get(collection_id)


@router.patch("/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: str,
    payload: CollectionUpdateRequest,
) -> CollectionResponse:
    return CollectionService().update(collection_id, payload.name, payload.parent_id)


@router.patch("/{collection_id}/move", response_model=CollectionResponse)
async def move_collection(
    collection_id: str,
    payload: CollectionMoveRequest,
) -> CollectionResponse:
    return CollectionService().move(collection_id, payload.parent_id)


@router.post("/bulk-move", status_code=HTTP_204_NO_CONTENT)
async def bulk_move(payload: BulkMoveRequest) -> None:
    CollectionService().bulk_move(
        collection_ids=payload.collection_ids,
        file_ids=payload.file_ids,
        target_collection_id=payload.target_collection_id,
    )


@router.delete("/{collection_id}", status_code=HTTP_204_NO_CONTENT)
async def delete_collection(collection_id: str) -> None:
    CollectionService().delete(collection_id)


@router.post("/{collection_id}/upload", response_model=FileResponse)
async def upload_file_to_collection(collection_id: str, file: UploadFile) -> FileResponse:
    CollectionService().get(collection_id)
    return await FileService().upload(file, collection_id=collection_id)

