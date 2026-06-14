from pathlib import Path
from uuid import uuid4

import pandas as pd

from app.core.config import get_settings
from app.repositories.query_repository import QueryRepository
from app.schemas.exports import ExportResponse


class ExportService:
    def __init__(self) -> None:
        settings = get_settings()
        self.exports_dir = Path(settings.workspace_dir) / "exports"
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        self.query_repository = QueryRepository()

    def export_query_result(self, query_id: str, file_format: str) -> ExportResponse:
        normalized_format = file_format.lower().strip()
        if normalized_format not in {"csv", "xlsx"}:
            raise ValueError("只支持 csv 或 xlsx 导出")

        query = self.query_repository.get_query(query_id)
        export_id = f"{uuid4().hex}.{normalized_format}"
        export_path = self.exports_dir / export_id
        dataframe = pd.DataFrame(query["rows"], columns=query["columns"])

        if normalized_format == "csv":
            dataframe.to_csv(export_path, index=False, encoding="utf-8-sig")
        else:
            dataframe.to_excel(export_path, index=False)

        return ExportResponse(
            exportId=export_id,
            fileName=f"dbfind-query-{query_id[:8]}.{normalized_format}",
            downloadUrl=f"/api/export/{export_id}",
        )

    def export_path(self, export_id: str) -> Path:
        if Path(export_id).name != export_id:
            raise FileNotFoundError(export_id)
        if Path(export_id).suffix.lower() not in {".csv", ".xlsx"}:
            raise FileNotFoundError(export_id)

        path = self.exports_dir / export_id
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(export_id)
        return path
