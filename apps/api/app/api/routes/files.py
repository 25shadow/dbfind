from fastapi import APIRouter, Form, UploadFile
from fastapi.concurrency import run_in_threadpool
from starlette.status import HTTP_204_NO_CONTENT

from app.schemas.files import (
    BulkUploadResponse,
    FileResponse,
    StructureCommitRequest,
    StructurePreviewResponse,
)
from app.services.file_service import FileService

router = APIRouter()


@router.post("/upload", response_model=FileResponse)
async def upload_file(file: UploadFile) -> FileResponse:
    return await FileService().upload(file)


@router.post("/bulk-upload", response_model=BulkUploadResponse)
async def bulk_upload_files(
    files: list[UploadFile],
    collection_id: str | None = Form(default=None, alias="collectionId"),
) -> BulkUploadResponse:
    return await FileService().bulk_upload(files, collection_id=collection_id)


@router.get("", response_model=list[FileResponse])
async def list_files() -> list[FileResponse]:
    return await run_in_threadpool(FileService().list_files)


@router.get("/{file_id}", response_model=FileResponse)
async def get_file(file_id: str) -> FileResponse:
    return await run_in_threadpool(FileService().get_file, file_id)


@router.get("/{file_id}/structure-preview", response_model=StructurePreviewResponse)
async def get_file_structure_preview(file_id: str, refresh: bool = False) -> StructurePreviewResponse:
    return await run_in_threadpool(FileService().get_structure_preview, file_id, refresh=refresh)


@router.post("/{file_id}/structure-commit", response_model=FileResponse)
async def commit_file_structure(file_id: str, payload: StructureCommitRequest) -> FileResponse:
    return await run_in_threadpool(FileService().commit_structure, file_id, payload)


@router.delete("/{file_id}", status_code=HTTP_204_NO_CONTENT)
async def delete_file(file_id: str) -> None:
    await run_in_threadpool(FileService().delete_file, file_id)
