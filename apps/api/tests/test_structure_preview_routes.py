from datetime import UTC, datetime

from fastapi.testclient import TestClient
from openpyxl import Workbook
import pandas as pd

from app.main import create_app
from app.repositories.file_repository import FileRepository
from app.repositories.sheet_repository import SheetRepository
from app.services.excel_parse_quality import ExcelParseQuality
from app.services.excel_structure_pipeline import ExcelStructurePipelineResult
from app.services.duckdb_service import DuckdbService


def test_file_structure_preview_route_returns_pipeline_results(temp_workspace):
    path = temp_workspace / "files" / "complex.xlsx"
    path.parent.mkdir(parents=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Complex"
    sheet["A1"] = "Report Title"
    sheet["C5"] = 2023
    sheet["E5"] = 2024
    sheet["C6"] = "Measure A"
    sheet["D6"] = "Measure B"
    sheet["E6"] = "Measure A"
    sheet["F6"] = "Measure B"
    sheet["C7"] = "Count"
    sheet["D7"] = "Ratio"
    sheet["E7"] = "Count"
    sheet["F7"] = "Ratio"
    sheet["A9"] = "Alpha"
    sheet["B9"] = "Alpha label"
    sheet["C9"] = 100
    sheet["D9"] = 0.2
    sheet["E9"] = 120
    sheet["F9"] = 0.3
    workbook.save(path)
    FileRepository().create_file(
        file_id="file-structure",
        name="complex.xlsx",
        path=str(path),
        file_hash="hash",
        status="needs_review",
        created_at=datetime.now(UTC).isoformat(),
    )

    response = TestClient(create_app()).get("/api/files/file-structure/structure-preview")

    assert response.status_code == 200
    body = response.json()
    assert body["fileId"] == "file-structure"
    assert body["items"][0]["sheetName"] == "Complex"
    assert body["items"][0]["blockRegion"] == "A1:F9"
    assert body["items"][0]["status"] == "needs_review"
    assert body["items"][0]["issues"] == ["vlm_model_missing"]
    assert body["items"][0]["plan"] is None
    assert body["items"][0]["columns"] == []
    assert body["items"][0]["previewRows"] == []
    assert body["items"][0]["sourceCellMap"] == {}


def test_file_structure_preview_route_returns_404_for_missing_file(temp_workspace):
    response = TestClient(create_app()).get("/api/files/missing/structure-preview")

    assert response.status_code == 404
    assert response.json()["detail"] == "文件不存在"


def test_file_structure_preview_route_returns_all_extracted_rows(temp_workspace, monkeypatch):
    path = temp_workspace / "files" / "rows.xlsx"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"placeholder")
    FileRepository().create_file(
        file_id="file-rows",
        name="rows.xlsx",
        path=str(path),
        file_hash="hash",
        status="needs_review",
        created_at=datetime.now(UTC).isoformat(),
    )

    def fake_parse(self, path):
        return [
            ExcelStructurePipelineResult(
                sheet_name="Rows",
                block_region="A1:B23",
                status="ready",
                issues=[],
                dataframe=pd.DataFrame(
                    [{"Name": f"City {index}", "Value": index} for index in range(1, 23)]
                ),
                quality=ExcelParseQuality("high", []),
            )
        ]

    monkeypatch.setattr("app.services.excel_structure_pipeline.ExcelStructurePipeline.parse", fake_parse)

    response = TestClient(create_app()).get("/api/files/file-rows/structure-preview")

    assert response.status_code == 200
    rows = response.json()["items"][0]["previewRows"]
    assert len(rows) == 22
    assert rows[-1] == {"Name": "City 22", "Value": 22}


def test_file_structure_preview_uses_saved_review_result_after_import(temp_workspace, monkeypatch):
    path = temp_workspace / "files" / "saved-review.xlsx"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"placeholder")
    FileRepository().create_file(
        file_id="file-saved-review",
        name="saved-review.xlsx",
        path=str(path),
        file_hash="hash",
        status="uploaded",
        created_at=datetime.now(UTC).isoformat(),
    )

    def fake_parse(self, path):
        return [
            ExcelStructurePipelineResult(
                sheet_name="Needs Review",
                block_region="A1:B2",
                status="needs_review",
                issues=["low_structure_confidence"],
                dataframe=pd.DataFrame([{"Name": "Alpha", "Value": 12}]),
                quality=ExcelParseQuality("low", ["low_structure_confidence"]),
                title="2-8 分行业地区生产总值",
                subtitle="Gross Domestic Product by Sector",
                unit="(100 million yuan)",
            )
        ]

    monkeypatch.setattr("app.services.excel_structure_pipeline.ExcelStructurePipeline.parse", fake_parse)
    from app.services.file_service import FileService

    FileService().import_to_duckdb("file-saved-review", str(path))
    monkeypatch.setattr(
        "app.services.excel_structure_pipeline.ExcelStructurePipeline.parse",
        lambda self, path: (_ for _ in ()).throw(RuntimeError("should not reparse")),
    )

    response = TestClient(create_app()).get("/api/files/file-saved-review/structure-preview")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["sheetName"] == "Needs Review"
    assert item["issues"] == ["low_structure_confidence"]
    assert item["title"] == "2-8 分行业地区生产总值"
    assert item["subtitle"] == "Gross Domestic Product by Sector"
    assert item["unit"] == "(100 million yuan)"
    assert item["previewRows"] == [{"Name": "Alpha", "Value": 12}]


def test_file_structure_preview_refresh_reparses_saved_result(temp_workspace, monkeypatch):
    path = temp_workspace / "files" / "refresh-review.xlsx"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"placeholder")
    FileRepository().create_file(
        file_id="file-refresh-review",
        name="refresh-review.xlsx",
        path=str(path),
        file_hash="hash",
        status="uploaded",
        created_at=datetime.now(UTC).isoformat(),
    )

    parse_results = [
        ExcelStructurePipelineResult(
            sheet_name="Old",
            block_region="A1:B2",
            status="needs_review",
            issues=["old_result"],
            dataframe=pd.DataFrame([{"Name": "Old", "Value": 1}]),
            quality=ExcelParseQuality("low", ["old_result"]),
        ),
        ExcelStructurePipelineResult(
            sheet_name="New",
            block_region="A1:B2",
            status="needs_review",
            issues=["new_result"],
            dataframe=pd.DataFrame([{"Name": "New", "Value": 2}]),
            quality=ExcelParseQuality("low", ["new_result"]),
        ),
    ]

    def fake_parse(self, path):
        return [parse_results.pop(0)]

    monkeypatch.setattr("app.services.excel_structure_pipeline.ExcelStructurePipeline.parse", fake_parse)
    from app.services.file_service import FileService

    FileService().import_to_duckdb("file-refresh-review", str(path))

    response = TestClient(create_app()).get("/api/files/file-refresh-review/structure-preview?refresh=true")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["sheetName"] == "New"
    assert item["issues"] == ["new_result"]


def test_file_structure_commit_writes_vlm_plan_to_duckdb(temp_workspace):
    path = temp_workspace / "files" / "commit.xlsx"
    path.parent.mkdir(parents=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet["A1"] = "Name"
    sheet["B1"] = 2024
    sheet["A2"] = "Alpha"
    sheet["B2"] = 12
    sheet["A4"] = "Note: keep raw note"
    workbook.save(path)
    FileRepository().create_file(
        file_id="file-commit",
        name="commit.xlsx",
        path=str(path),
        file_hash="hash",
        status="needs_review",
        created_at=datetime.now(UTC).isoformat(),
    )

    response = TestClient(create_app()).post(
        "/api/files/file-commit/structure-commit",
        json={
            "items": [
                {
                    "sheetName": "Sheet1",
                    "plan": {
                        "tableRegion": "A1:B2",
                        "titleRows": [],
                        "unitCells": [],
                        "headerRows": [1],
                        "dataStartRow": 2,
                        "dataEndRow": 2,
                        "rowHeaderColumns": ["A"],
                        "valueColumns": ["B"],
                        "categoryRows": [],
                        "orientation": "wide_table",
                        "confidence": 0.9,
                        "source": "vlm",
                    },
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    sheets = SheetRepository().list_sheets("file-commit")
    assert [(sheet["name"], sheet["row_count"], sheet["column_count"]) for sheet in sheets] == [
        ("Sheet1", 1, 2)
    ]
    rows = DuckdbService().preview_table(
        DuckdbService().database_path_for_file("file-commit"),
        sheets[0]["table_name"],
        10,
    )
    assert rows == [{"Name": "Alpha", "2024": 12}]
