from app.core.config import get_settings
from app.repositories.sheet_repository import SheetRepository
from app.schemas.sheets import SheetPreviewResponse, SheetResponse
from app.services.duckdb_service import DuckdbService


class SheetService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.repository = SheetRepository()
        self.duckdb_service = DuckdbService()

    def list_sheets(self, file_id: str) -> list[SheetResponse]:
        return [SheetResponse(**row) for row in self.repository.list_sheets(file_id)]

    def preview_sheet(self, sheet_id: str) -> SheetPreviewResponse:
        sheet = self.repository.get_sheet(sheet_id)
        database_path = self.duckdb_service.database_path_for_file(sheet["file_id"])
        rows = self.duckdb_service.preview_table(
            database_path,
            sheet["table_name"],
            self.settings.max_preview_rows,
        )
        columns = list(rows[0].keys()) if rows else []
        return SheetPreviewResponse(sheet_id=sheet_id, columns=columns, rows=rows)
