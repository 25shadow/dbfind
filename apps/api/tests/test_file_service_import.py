from datetime import UTC, datetime

import pandas as pd
from openpyxl import Workbook

from app.repositories.file_repository import FileRepository
from app.repositories.sheet_repository import SheetRepository
from app.schemas.files import StructureCommitRequest
from app.schemas.table_structure import TableStructurePlan
from app.services.duckdb_service import DuckdbService
from app.services.excel_parse_quality import ExcelParseQuality
from app.services.excel_structure_pipeline import ExcelStructurePipelineResult
from app.services.file_service import FileService


def test_excel_import_auto_writes_ready_vlm_structure_to_duckdb(
    temp_workspace,
    reset_settings_cache,
    monkeypatch,
) -> None:
    file_id = "file-1"
    path = temp_workspace / "files" / "multi-table.xlsx"
    path.parent.mkdir(parents=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet["A1"] = "2-2  地区生产总值"
    sheet["A2"] = "Gross Domestic Product"
    sheet["A4"] = "单位：亿元"
    sheet["B4"] = "(100 million yuan)"
    sheet["A5"] = "Name"
    sheet["B5"] = "Value"
    sheet["A6"] = "Alpha"
    sheet["B6"] = 12
    workbook.save(path)
    workbook.close()

    FileRepository().create_file(
        file_id=file_id,
        name="multi-table.xlsx",
        path=str(path),
        file_hash="hash",
        status="uploaded",
        created_at=datetime.now(UTC).isoformat(),
    )
    plan = TableStructurePlan(
        tableRegion="A1:B6",
        titleRows=[1, 2],
        unitCells=["A4", "B4"],
        headerRows=[5],
        dataStartRow=6,
        dataEndRow=6,
        rowHeaderColumns=["A"],
        valueColumns=["B"],
        confidence=0.92,
        source="vlm",
    )

    def fake_parse(self, path):
        return [
            ExcelStructurePipelineResult(
                sheet_name="Sheet1",
                block_region="A1:B2",
                status="ready",
                issues=[],
                plan=plan,
                dataframe=pd.DataFrame([{"Name": "Alpha", "Value": 12}]),
                quality=ExcelParseQuality("high", []),
                raw_content_blocks=[
                    {"region": "A1:A1", "text": "2-2  地区生产总值", "cells": ["A1"]},
                    {"region": "A2:A2", "text": "Gross Domestic Product", "cells": ["A2"]},
                    {"region": "A4:B4", "text": "单位：亿元 (100 million yuan)", "cells": ["A4", "B4"]},
                ],
            )
        ]

    monkeypatch.setattr("app.services.excel_structure_pipeline.ExcelStructurePipeline.parse", fake_parse)

    FileService().import_to_duckdb(file_id, str(path))

    assert FileRepository().get_file(file_id)["status"] == "ready"
    sheets = SheetRepository().list_sheets(file_id)
    assert [(sheet["name"], sheet["row_count"], sheet["column_count"]) for sheet in sheets] == [
        ("Sheet1", 1, 2)
    ]
    assert sheets[0]["title"] == "2-2 地区生产总值"
    assert sheets[0]["subtitle"] == "Gross Domestic Product"
    assert sheets[0]["unit"] == "单位：亿元 (100 million yuan)"
    rows = DuckdbService().preview_table(
        DuckdbService().database_path_for_file(file_id),
        sheets[0]["table_name"],
        5,
    )
    assert rows == [{"Name": "Alpha", "Value": 12}]


def test_csv_import_still_writes_structured_table(
    temp_workspace,
    reset_settings_cache,
) -> None:
    file_id = "csv-1"
    path = temp_workspace / "files" / "plain.csv"
    path.parent.mkdir(parents=True)
    path.write_text("name,value\nAlpha,12\n", encoding="utf-8")
    FileRepository().create_file(
        file_id=file_id,
        name="plain.csv",
        path=str(path),
        file_hash="hash",
        status="uploaded",
        created_at=datetime.now(UTC).isoformat(),
    )

    FileService().import_to_duckdb(file_id, str(path))

    assert FileRepository().get_file(file_id)["status"] == "ready"
    sheets = SheetRepository().list_sheets(file_id)
    assert [(sheet["name"], sheet["row_count"], sheet["column_count"]) for sheet in sheets] == [
        ("plain", 1, 2),
    ]
    rows = DuckdbService().preview_table(
        DuckdbService().database_path_for_file(file_id),
        sheets[0]["table_name"],
        5,
    )
    assert rows == [{"name": "Alpha", "value": 12}]


def test_import_marks_readable_but_low_confidence_file_as_needs_review(
    temp_workspace,
    reset_settings_cache,
    monkeypatch,
) -> None:
    file_id = "file-review"
    path = temp_workspace / "files" / "complex.xlsx"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"placeholder")
    FileRepository().create_file(
        file_id=file_id,
        name="complex.xlsx",
        path=str(path),
        file_hash="hash",
        status="uploaded",
        created_at=datetime.now(UTC).isoformat(),
    )
    def fake_parse(self, path):
        return [
            ExcelStructurePipelineResult(
                sheet_name="Review",
                block_region="A1:B2",
                status="needs_review",
                issues=["low_structure_confidence"],
                dataframe=pd.DataFrame([{"Name": "Alpha", "Value": 12}]),
                quality=ExcelParseQuality("low", ["low_structure_confidence"]),
            )
        ]

    monkeypatch.setattr("app.services.excel_structure_pipeline.ExcelStructurePipeline.parse", fake_parse)

    FileService().import_to_duckdb(file_id, str(path))

    assert FileRepository().get_file(file_id)["status"] == "needs_review"
    assert SheetRepository().list_sheets(file_id) == []


def test_commit_structure_preserves_title_subtitle_and_unit_metadata(
    temp_workspace,
    reset_settings_cache,
) -> None:
    file_id = "manual-commit"
    path = temp_workspace / "files" / "manual.xlsx"
    path.parent.mkdir(parents=True)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet["A1"] = "2-2  地区生产总值"
    sheet["A2"] = "Gross Domestic Product"
    sheet["A3"] = "单位：亿元 (100 million yuan)"
    sheet["A4"] = "指标"
    sheet["B4"] = "Item"
    sheet["C4"] = 2024
    sheet["A5"] = "地区生产总值"
    sheet["B5"] = "Gross Domestic Product"
    sheet["C5"] = 141633.8068
    workbook.save(path)
    workbook.close()

    FileRepository().create_file(
        file_id=file_id,
        name="manual.xlsx",
        path=str(path),
        file_hash="hash",
        status="needs_review",
        created_at=datetime.now(UTC).isoformat(),
    )

    plan = TableStructurePlan(
        tableRegion="A1:C5",
        titleRows=[1, 2],
        unitCells=["A3"],
        headerRows=[4],
        dataStartRow=5,
        dataEndRow=5,
        rowHeaderColumns=["A", "B"],
        valueColumns=["C"],
        confidence=0.9,
        source="manual",
    )

    FileService().commit_structure(
        file_id,
        StructureCommitRequest(items=[{"sheetName": "Sheet1", "plan": plan}]),
    )

    sheets = SheetRepository().list_sheets(file_id)
    assert sheets[0]["title"] == "2-2 地区生产总值"
    assert sheets[0]["subtitle"] == "Gross Domestic Product"
    assert sheets[0]["unit"] == "单位：亿元 (100 million yuan)"
