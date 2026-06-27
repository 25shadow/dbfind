from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.core.config import get_settings
from app.schemas.table_structure import TableStructurePlan
from app.services.excel_cell_grid import RawCellGrid, RawCellGridExtractor
from app.services.excel_parse_quality import ExcelParseQuality, ExcelParseQualityEvaluator
from app.services.sheet_renderer import SheetRenderer
from app.services.structure_plan_extractor import StructurePlanExtractor
from app.services.table_metadata_extractor import TableMetadataExtractor
from app.services.table_structure_validator import TableStructureValidator
from app.services.vision_structure_planner import VisionStructurePlanner


@dataclass(frozen=True)
class ExcelStructurePipelineResult:
    sheet_name: str
    block_region: str | None
    status: str
    issues: list[str]
    plan: TableStructurePlan | None = None
    dataframe: pd.DataFrame = field(default_factory=pd.DataFrame)
    quality: ExcelParseQuality = field(default_factory=lambda: ExcelParseQuality("low", []))
    source_cell_map: dict[str, list[str]] = field(default_factory=dict)
    raw_content_blocks: list[dict[str, object]] = field(default_factory=list)
    title: str | None = None
    subtitle: str | None = None
    unit: str | None = None


class ExcelStructurePipeline:
    """VLM-first structure-plan parsing pipeline for complex spreadsheets."""

    def __init__(self, vision_planner: VisionStructurePlanner | None = None) -> None:
        self.settings = get_settings()
        self.grid_extractor = RawCellGridExtractor()
        self.sheet_renderer = SheetRenderer()
        self.vision_planner = vision_planner or VisionStructurePlanner()
        self.plan_validator = TableStructureValidator()
        self.plan_extractor = StructurePlanExtractor()
        self.quality_evaluator = ExcelParseQualityEvaluator()
        self.table_metadata_extractor = TableMetadataExtractor()

    def parse(self, path: str) -> list[ExcelStructurePipelineResult]:
        results: list[ExcelStructurePipelineResult] = []
        for grid in self.grid_extractor.extract(path):
            if not any(cell.value not in (None, "") for cell in grid.cells):
                continue
            results.append(self._parse_sheet(grid))
        return results

    def _parse_sheet(self, grid: RawCellGrid) -> ExcelStructurePipelineResult:
        rendering = self.sheet_renderer.render(grid)
        try:
            plan = self.vision_planner.plan(grid, rendering)
        except Exception as exc:
            return self._review_result(
                grid.sheet_name,
                rendering.region,
                [f"vlm_structure_planner_failed: {exc}"],
            )
        if plan is None:
            issue = self.vision_planner.availability_issue() or "vlm_structure_plan_not_found"
            return self._review_result(
                grid.sheet_name,
                rendering.region,
                [issue],
            )

        metadata = self.table_metadata_extractor.extract_from_grid_plan(grid, plan)
        validation = self.plan_validator.validate(grid, plan)
        if not validation.is_valid:
            return self._review_result(
                grid.sheet_name,
                rendering.region,
                validation.issues,
                plan=plan,
                metadata=metadata,
            )

        extracted = self.plan_extractor.extract(grid, plan)
        quality = self.quality_evaluator.evaluate(extracted.dataframe)
        issues = list(quality.issues)
        confidence_threshold = self.settings.structure_confidence_threshold
        if plan.confidence < confidence_threshold:
            issues.append("low_structure_confidence")
        status = "ready" if quality.is_importable and plan.confidence >= confidence_threshold else "needs_review"
        return ExcelStructurePipelineResult(
            sheet_name=grid.sheet_name,
            block_region=plan.table_region,
            status=status,
            issues=issues,
            plan=plan,
            dataframe=extracted.dataframe,
            quality=quality,
            source_cell_map=extracted.source_cell_map,
            raw_content_blocks=self._raw_content_blocks(grid, plan),
            title=metadata["title"],
            subtitle=metadata["subtitle"],
            unit=metadata["unit"],
        )

    def _review_result(
        self,
        sheet_name: str,
        block_region: str | None,
        issues: list[str],
        plan: TableStructurePlan | None = None,
        metadata: dict[str, str | None] | None = None,
    ) -> ExcelStructurePipelineResult:
        metadata = metadata or {"title": None, "subtitle": None, "unit": None}
        return ExcelStructurePipelineResult(
            sheet_name=sheet_name,
            block_region=block_region,
            status="needs_review",
            issues=issues,
            plan=plan,
            quality=ExcelParseQuality("low", issues),
            title=metadata["title"],
            subtitle=metadata["subtitle"],
            unit=metadata["unit"],
        )

    def _raw_content_blocks(self, grid: RawCellGrid, plan: TableStructurePlan) -> list[dict[str, object]]:
        data_cols = {
            self._column_index(column)
            for column in [*plan.row_header_columns, *plan.value_columns]
        }
        data_end = plan.data_end_row or grid.max_row
        blocks = []
        for row_index in range(1, grid.max_row + 1):
            cells = [
                cell
                for cell in sorted((cell for cell in grid.cells if cell.row == row_index), key=lambda item: item.col)
                if cell.value not in (None, "")
                and not (plan.data_start_row <= cell.row <= data_end and cell.col in data_cols)
            ]
            if not cells:
                continue
            blocks.append(
                {
                    "region": f"{cells[0].address}:{cells[-1].address}",
                    "text": " ".join(str(cell.value).strip() for cell in cells if str(cell.value).strip()),
                    "cells": [cell.address for cell in cells],
                }
            )
        return blocks

    def _column_index(self, letter: str) -> int:
        result = 0
        for char in letter.upper():
            result = result * 26 + ord(char) - ord("A") + 1
        return result
