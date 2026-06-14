from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.core.config import get_settings
from app.repositories.collection_repository import CollectionRepository
from app.repositories.column_repository import ColumnRepository
from app.repositories.file_repository import FileRepository
from app.repositories.sheet_repository import SheetRepository
from app.repositories.structure_preview_repository import StructurePreviewRepository
from app.repositories.table_catalog_repository import TableCatalogRepository
from app.schemas.files import (
    BulkUploadResponse,
    FileResponse,
    StructureCommitRequest,
    StructurePreviewItemResponse,
    StructurePreviewResponse,
)
from app.services.duckdb_service import DuckdbService
from app.services.excel_cell_grid import RawCellGrid, RawCellGridExtractor
from app.services.excel_loader import ExcelLoader
from app.services.excel_structure_pipeline import ExcelStructurePipeline, ExcelStructurePipelineResult
from app.services.schema_service import SchemaService
from app.services.structure_plan_extractor import StructurePlanExtractor
from app.services.table_structure_validator import TableStructureValidator
from app.services.table_metadata_extractor import TableMetadataExtractor

ALLOWED_FILE_EXTENSIONS = {".csv", ".et", ".ods", ".xls", ".xlsb", ".xlsm", ".xlsx"}
SUPPORTED_FILE_TYPES_TEXT = ".xlsx、.xls、.xlsm、.xlsb、.et、.ods 和 .csv"


class FileService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.repository = FileRepository()
        self.collection_repository = CollectionRepository()
        self.sheet_repository = SheetRepository()
        self.column_repository = ColumnRepository()
        self.structure_preview_repository = StructurePreviewRepository()
        self.table_catalog_repository = TableCatalogRepository()
        self.excel_loader = ExcelLoader()
        self.excel_structure_pipeline = ExcelStructurePipeline()
        self.grid_extractor = RawCellGridExtractor()
        self.structure_plan_extractor = StructurePlanExtractor()
        self.table_structure_validator = TableStructureValidator()
        self.table_metadata_extractor = TableMetadataExtractor()
        self.duckdb_service = DuckdbService()
        self.schema_service = SchemaService()
        self.files_dir = Path(self.settings.workspace_dir) / "files"
        self.files_dir.mkdir(parents=True, exist_ok=True)

    async def upload(self, file: UploadFile, collection_id: str | None = None) -> FileResponse:
        if collection_id:
            try:
                self.collection_repository.get_collection(collection_id)
            except FileNotFoundError as exc:
                raise HTTPException(status_code=404, detail="资料文件夹不存在") from exc

        original_name = file.filename or "unknown"
        extension = Path(original_name).suffix.lower()

        if extension not in ALLOWED_FILE_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"只支持 {SUPPORTED_FILE_TYPES_TEXT} 文件")

        file_id = uuid4().hex
        stored_path = self.files_dir / f"{file_id}{extension}"
        digest = sha256()

        with stored_path.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                digest.update(chunk)
                output.write(chunk)

        created_at = datetime.now(UTC).isoformat()
        self.repository.create_file(
            file_id=file_id,
            name=original_name,
            path=str(stored_path),
            file_hash=digest.hexdigest(),
            status="uploaded",
            created_at=created_at,
            collection_id=collection_id,
        )
        self.import_to_duckdb(file_id, str(stored_path))
        return self._to_response(self.repository.get_file(file_id))

    async def bulk_upload(
        self,
        files: list[UploadFile],
        collection_id: str | None = None,
    ) -> BulkUploadResponse:
        if not files:
            raise HTTPException(status_code=400, detail="请选择至少一个文件")

        results = []
        for file in files:
            file_name = file.filename or "unknown"
            try:
                uploaded_file = await self.upload(file, collection_id=collection_id)
                results.append(
                    {
                        "fileName": file_name,
                        "success": True,
                        "file": uploaded_file,
                        "error": None,
                    }
                )
            except HTTPException as exc:
                results.append(
                    {
                        "fileName": file_name,
                        "success": False,
                        "file": None,
                        "error": str(exc.detail),
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "fileName": file_name,
                        "success": False,
                        "file": None,
                        "error": str(exc) or "文件导入失败",
                    }
                )

        success_count = sum(1 for item in results if item["success"])
        return BulkUploadResponse(
            summary={
                "total": len(results),
                "success": success_count,
                "failed": len(results) - success_count,
            },
            results=results,
        )

    def import_to_duckdb(self, file_id: str, path: str) -> None:
        self.repository.update_status(file_id, "importing")
        database_path = self.duckdb_service.database_path_for_file(file_id)
        extension = Path(path).suffix.lower()
        if extension != ".csv":
            self.sheet_repository.replace_sheets(file_id, [])
            self.schema_service.build_for_file(file_id)
            self._auto_import_excel_structure(file_id, path)
            return

        sheets = []
        try:
            loaded_sheets = self.excel_loader.load(path)
            loaded_sheets = [
                sheet
                for sheet in loaded_sheets
                if len(sheet.dataframe.index) > 0 and len(sheet.dataframe.columns) > 0
            ]
            if not loaded_sheets:
                self.repository.update_status(file_id, "needs_review")
                return
            used_table_names: set[str] = set()

            for index, loaded_sheet in enumerate(loaded_sheets, start=1):
                base_name = self.duckdb_service.normalize_table_name(
                    loaded_sheet.name,
                    fallback=f"sheet_{index}",
                )
                table_name = base_name
                suffix = 2
                while table_name in used_table_names:
                    table_name = f"{base_name}_{suffix}"
                    suffix += 1
                used_table_names.add(table_name)

                self.duckdb_service.write_dataframe(
                    database_path,
                    table_name,
                    loaded_sheet.dataframe,
                )
                sheets.append(
                    {
                        "id": f"{file_id}_{index}",
                        "name": loaded_sheet.name,
                        "table_name": table_name,
                        "row_count": len(loaded_sheet.dataframe),
                        "column_count": len(loaded_sheet.dataframe.columns),
                        "title": loaded_sheet.title,
                        "subtitle": loaded_sheet.subtitle,
                        "unit": loaded_sheet.unit,
                    }
                )

            self.sheet_repository.replace_sheets(file_id, sheets)
            self.schema_service.build_for_file(file_id)
            self.repository.update_status(file_id, "ready")
        except Exception:
            self.repository.update_status(file_id, "failed")
            raise

    def _auto_import_excel_structure(self, file_id: str, path: str) -> None:
        try:
            structure_results = self.excel_structure_pipeline.parse(path)
        except Exception:
            self.repository.update_status(file_id, "failed")
            raise

        self._save_structure_preview(file_id, structure_results)
        if not structure_results or not all(
            result.status == "ready" and result.plan is not None and not result.dataframe.empty
            for result in structure_results
        ):
            self.repository.update_status(file_id, "needs_review")
            return

        self._write_structure_results_to_duckdb(file_id, structure_results)
        self.structure_preview_repository.delete(file_id)
        self.repository.update_status(file_id, "ready")

    def _write_structure_results_to_duckdb(
        self,
        file_id: str,
        structure_results: list[ExcelStructurePipelineResult],
    ) -> None:
        database_path = self.duckdb_service.database_path_for_file(file_id)
        data_file = self.repository.get_file(file_id)
        grids_by_name = {grid.sheet_name: grid for grid in self.grid_extractor.extract(data_file["path"])}
        sheets = []
        used_table_names: set[str] = set()

        for index, result in enumerate(structure_results, start=1):
            base_name = self.duckdb_service.normalize_table_name(
                result.sheet_name,
                fallback=f"sheet_{index}",
            )
            table_name = base_name
            suffix = 2
            while table_name in used_table_names:
                table_name = f"{base_name}_{suffix}"
                suffix += 1
            used_table_names.add(table_name)

            self.duckdb_service.write_dataframe(database_path, table_name, result.dataframe)
            grid = grids_by_name.get(result.sheet_name)
            metadata = self._metadata_for_structure_result(result, grid)
            sheets.append(
                {
                    "id": f"{file_id}_{index}",
                    "name": result.sheet_name,
                    "table_name": table_name,
                    "row_count": len(result.dataframe),
                    "column_count": len(result.dataframe.columns),
                    "title": metadata["title"],
                    "subtitle": metadata["subtitle"],
                    "unit": metadata["unit"],
                }
            )

        self.sheet_repository.replace_sheets(file_id, sheets)
        self.schema_service.build_for_file(file_id)

    def _save_structure_preview(
        self,
        file_id: str,
        structure_results: list[ExcelStructurePipelineResult],
    ) -> None:
        payload = StructurePreviewResponse(
            fileId=file_id,
            items=[
                self._structure_result_to_response(result)
                for result in structure_results
            ],
        ).model_dump(by_alias=True)
        self.structure_preview_repository.save(
            file_id,
            payload,
            datetime.now(UTC).isoformat(),
        )

    def list_files(self) -> list[FileResponse]:
        return [self._to_response(row) for row in self.repository.list_files()]

    def get_file(self, file_id: str) -> FileResponse:
        try:
            return self._to_response(self.repository.get_file(file_id))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="文件不存在") from exc

    def get_structure_preview(self, file_id: str, refresh: bool = False) -> StructurePreviewResponse:
        try:
            data_file = self.repository.get_file(file_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="文件不存在") from exc

        cached = None if refresh else self.structure_preview_repository.get(file_id)
        if cached is not None:
            return StructurePreviewResponse(**cached)

        try:
            structure_results = self.excel_structure_pipeline.parse(data_file["path"])
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"结构预览生成失败：{exc}") from exc

        self._save_structure_preview(file_id, structure_results)
        cached = self.structure_preview_repository.get(file_id)
        if cached is not None:
            return StructurePreviewResponse(**cached)
        items = [self._structure_result_to_response(result) for result in structure_results]
        return StructurePreviewResponse(fileId=file_id, items=items)

    def commit_structure(self, file_id: str, payload: StructureCommitRequest) -> FileResponse:
        try:
            data_file = self.repository.get_file(file_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="文件不存在") from exc

        if not payload.items:
            raise HTTPException(status_code=400, detail="没有可导入的结构计划")

        grids_by_name = {grid.sheet_name: grid for grid in self.grid_extractor.extract(data_file["path"])}
        database_path = self.duckdb_service.database_path_for_file(file_id)
        sheets = []
        used_table_names: set[str] = set()

        for index, item in enumerate(payload.items, start=1):
            grid = grids_by_name.get(item.sheet_name)
            if grid is None:
                raise HTTPException(status_code=400, detail=f"找不到 Sheet：{item.sheet_name}")
            validation = self.table_structure_validator.validate(grid, item.plan)
            if not validation.is_valid:
                raise HTTPException(status_code=400, detail=f"结构计划不合法：{', '.join(validation.issues)}")

            extracted = self.structure_plan_extractor.extract(grid, item.plan)
            if extracted.dataframe.empty:
                raise HTTPException(status_code=400, detail=f"{item.sheet_name} 没有抽取出数据")

            base_name = self.duckdb_service.normalize_table_name(
                item.sheet_name,
                fallback=f"sheet_{index}",
            )
            table_name = base_name
            suffix = 2
            while table_name in used_table_names:
                table_name = f"{base_name}_{suffix}"
                suffix += 1
            used_table_names.add(table_name)

            self.duckdb_service.write_dataframe(database_path, table_name, extracted.dataframe)
            metadata = self.table_metadata_extractor.extract_from_grid_plan(grid, item.plan)
            sheets.append(
                {
                    "id": f"{file_id}_{index}",
                    "name": item.sheet_name,
                    "table_name": table_name,
                    "row_count": len(extracted.dataframe),
                    "column_count": len(extracted.dataframe.columns),
                    "title": metadata["title"],
                    "subtitle": metadata["subtitle"],
                    "unit": metadata["unit"],
                }
            )

        self.sheet_repository.replace_sheets(file_id, sheets)
        self.schema_service.build_for_file(file_id)
        self.structure_preview_repository.delete(file_id)
        self.repository.update_status(file_id, "ready")
        return self._to_response(self.repository.get_file(file_id))

    def _metadata_for_structure_result(
        self,
        result: ExcelStructurePipelineResult,
        grid: RawCellGrid | None,
    ) -> dict[str, str | None]:
        metadata = {"title": result.title, "subtitle": result.subtitle, "unit": result.unit}
        if any(metadata.values()):
            return metadata
        if grid is not None and result.plan is not None:
            return self.table_metadata_extractor.extract_from_grid_plan(grid, result.plan)
        return self.table_metadata_extractor.extract(result.raw_content_blocks)

    def delete_file(self, file_id: str) -> None:
        try:
            data_file = self.repository.get_file(file_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="文件不存在") from exc

        sheets = self.sheet_repository.list_sheets(file_id)
        self.column_repository.delete_by_sheet_ids([sheet["id"] for sheet in sheets])
        self.table_catalog_repository.delete_by_file(file_id)
        self.structure_preview_repository.delete(file_id)
        self.sheet_repository.delete_by_file(file_id)
        self.repository.delete_file(file_id)

        self._delete_path_if_exists(Path(data_file["path"]))
        self._delete_path_if_exists(self.duckdb_service.database_path_for_file(file_id))

    def _delete_path_if_exists(self, path: Path) -> None:
        if path.exists() and path.is_file():
            path.unlink()

    def _to_response(self, data_file: dict) -> FileResponse:
        data = dict(data_file)
        collection_id = data.get("collection_id")
        data["collection_name"] = None
        if collection_id:
            try:
                data["collection_name"] = self.collection_repository.get_collection(collection_id)[
                    "name"
                ]
            except FileNotFoundError:
                data["collection_id"] = None
        return FileResponse(**data)

    def _structure_result_to_response(
        self,
        result: ExcelStructurePipelineResult,
    ) -> StructurePreviewItemResponse:
        return StructurePreviewItemResponse(
            sheetName=result.sheet_name,
            blockRegion=result.block_region,
            status=result.status,
            issues=result.issues,
            qualityConfidence=result.quality.confidence,
            title=result.title,
            subtitle=result.subtitle,
            unit=result.unit,
            plan=result.plan,
            columns=[str(column) for column in result.dataframe.columns],
            previewRows=result.dataframe.to_dict(orient="records"),
            sourceCellMap=result.source_cell_map,
            rawContentBlocks=result.raw_content_blocks,
        )
