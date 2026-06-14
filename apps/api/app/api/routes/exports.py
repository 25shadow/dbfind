from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.schemas.exports import ExportRequest, ExportResponse
from app.services.export_service import ExportService

router = APIRouter()


@router.post("", response_model=ExportResponse)
async def create_export(payload: ExportRequest) -> ExportResponse:
    try:
        return ExportService().export_query_result(payload.query_id, payload.file_format)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="查询不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{export_id}")
async def get_export(export_id: str) -> FileResponse:
    try:
        export_path = ExportService().export_path(export_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="导出文件不存在") from exc

    return FileResponse(
        export_path,
        filename=f"dbfind-{export_id}",
        media_type="application/octet-stream",
    )
