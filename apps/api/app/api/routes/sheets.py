from fastapi import APIRouter, HTTPException

from app.schemas.sheets import SheetPreviewResponse, SheetResponse
from app.services.schema_service import SchemaService
from app.services.sheet_service import SheetService

router = APIRouter()


@router.get("/files/{file_id}/sheets", response_model=list[SheetResponse])
async def list_sheets(file_id: str) -> list[SheetResponse]:
    return SheetService().list_sheets(file_id)


@router.get("/sheets/{sheet_id}/preview", response_model=SheetPreviewResponse)
async def preview_sheet(sheet_id: str) -> SheetPreviewResponse:
    try:
        return SheetService().preview_sheet(sheet_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Sheet 不存在") from exc


@router.get("/files/{file_id}/schema")
async def get_file_schema(file_id: str) -> dict[str, str]:
    return {"schema": SchemaService().build_schema_text(file_id)}
