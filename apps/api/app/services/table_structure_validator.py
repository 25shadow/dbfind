from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.schemas.table_structure import TableStructurePlan
from app.services.excel_cell_grid import RawCellGrid


@dataclass(frozen=True)
class TableStructureValidationResult:
    is_valid: bool
    issues: list[str] = field(default_factory=list)


class TableStructureValidator:
    """Validate coordinate plans before deterministic cell extraction."""

    def validate(self, grid: RawCellGrid, plan: TableStructurePlan) -> TableStructureValidationResult:
        issues: list[str] = []
        row_header_cols = self._column_indexes(plan.row_header_columns, issues)
        value_cols = self._column_indexes(plan.value_columns, issues)
        table_bounds = self._region_bounds(plan.table_region, issues)

        if not plan.header_rows:
            issues.append("header_rows_empty")
        if plan.data_start_row < 1:
            issues.append("data_start_row_out_of_range")
        if plan.data_end_row is not None and plan.data_end_row < plan.data_start_row:
            issues.append("data_end_before_data_start")
        if not row_header_cols:
            issues.append("row_header_columns_empty")
        if not value_cols:
            issues.append("value_columns_empty")

        data_end = plan.data_end_row or grid.max_row
        if plan.data_start_row > grid.max_row or data_end > grid.max_row:
            issues.append("data_rows_out_of_grid")
        if any(row >= plan.data_start_row for row in plan.header_rows):
            issues.append("header_overlaps_data")
        if any(col > grid.max_col for col in row_header_cols + value_cols):
            issues.append("columns_out_of_grid")
        if set(row_header_cols) & set(value_cols):
            issues.append("row_header_and_value_columns_overlap")

        if table_bounds is not None:
            min_col, min_row, max_col, max_row = table_bounds
            if min_row < 1 or max_row > grid.max_row or min_col < 1 or max_col > grid.max_col:
                issues.append("table_region_out_of_grid")
            if not all(min_row <= row <= max_row for row in plan.header_rows):
                issues.append("header_rows_outside_table_region")
            if not (min_row <= plan.data_start_row <= max_row):
                issues.append("data_start_outside_table_region")
            if plan.data_end_row is not None and not (min_row <= plan.data_end_row <= max_row):
                issues.append("data_end_outside_table_region")
            if not all(min_col <= col <= max_col for col in row_header_cols + value_cols):
                issues.append("columns_outside_table_region")

        if value_cols and not self._has_any_value_cell(grid, plan.data_start_row, data_end, value_cols):
            issues.append("value_columns_without_data")
        if row_header_cols and not self._has_any_value_cell(grid, plan.data_start_row, data_end, row_header_cols):
            issues.append("row_header_columns_without_data")

        return TableStructureValidationResult(is_valid=not issues, issues=issues)

    def _has_any_value_cell(self, grid: RawCellGrid, start_row: int, end_row: int, cols: list[int]) -> bool:
        return any(
            cell.value not in (None, "")
            for cell in grid.cells
            if start_row <= cell.row <= end_row and cell.col in cols
        )

    def _column_indexes(self, columns: list[str], issues: list[str]) -> list[int]:
        indexes = []
        for column in columns:
            try:
                indexes.append(self._column_index(column))
            except ValueError:
                issues.append("invalid_column_reference")
        return indexes

    def _region_bounds(self, region: str, issues: list[str]) -> tuple[int, int, int, int] | None:
        match = re.fullmatch(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", region.upper().strip())
        if not match:
            issues.append("invalid_table_region")
            return None
        start_col, start_row, end_col, end_row = match.groups()
        min_col = self._column_index(start_col)
        max_col = self._column_index(end_col)
        min_row = int(start_row)
        max_row = int(end_row)
        if min_col > max_col or min_row > max_row:
            issues.append("inverted_table_region")
        return min_col, min_row, max_col, max_row

    def _column_index(self, letter: str) -> int:
        if not letter or not re.fullmatch(r"[A-Za-z]+", letter):
            raise ValueError(f"Invalid column letter: {letter}")
        result = 0
        for char in letter.upper():
            result = result * 26 + ord(char) - ord("A") + 1
        return result
