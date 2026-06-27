from __future__ import annotations

from dataclasses import dataclass
import re

import pandas as pd

from app.schemas.table_structure import TableStructurePlan
from app.services.excel_cell_grid import RawCell, RawCellGrid


@dataclass(frozen=True)
class ExtractedTable:
    dataframe: pd.DataFrame
    source_cell_map: dict[str, list[str]]


class StructurePlanExtractor:
    """Extract table data from real cells according to a coordinate structure plan."""

    def extract(self, grid: RawCellGrid, plan: TableStructurePlan) -> ExtractedTable:
        row_header_cols = [self._column_index(col) for col in plan.row_header_columns]
        value_cols = [self._column_index(col) for col in plan.value_columns]
        all_cols = row_header_cols + value_cols
        data_end = plan.data_end_row or grid.max_row
        columns = self._column_names(grid, plan, row_header_cols, value_cols)
        rows = []
        source_cell_map = {column: [] for column in columns}

        for row_index in range(plan.data_start_row, data_end + 1):
            values = []
            has_value = False
            for column_name, col_index in zip(columns, all_cols):
                cell = self._cell_at(grid, row_index, col_index)
                value = self._cell_extract_value(cell)
                values.append(value)
                if value not in (None, ""):
                    has_value = True
                    source_cell_map[column_name].append(cell.address if cell else self._address(row_index, col_index))
            if has_value:
                rows.append(values)

        return ExtractedTable(
            dataframe=pd.DataFrame(rows, columns=columns),
            source_cell_map=source_cell_map,
        )

    def _column_names(
        self,
        grid: RawCellGrid,
        plan: TableStructurePlan,
        row_header_cols: list[int],
        value_cols: list[int],
    ) -> list[str]:
        header_rows = self._effective_header_rows(grid, plan, row_header_cols + value_cols)
        row_header_names = [
            self._row_header_name(grid, header_rows, col_index)
            for col_index in row_header_cols
        ]
        value_names = [
            self._value_header_name(grid, header_rows, col_index, set(plan.header_rows))
            for col_index in value_cols
        ]
        return self._dedupe_names(row_header_names + value_names)

    def _effective_header_rows(
        self,
        grid: RawCellGrid,
        plan: TableStructurePlan,
        data_cols: list[int],
    ) -> list[int]:
        header_rows = sorted(set(plan.header_rows))
        if not header_rows:
            return []

        table_min_row = self._region_min_row(plan.table_region)
        first_header = header_rows[0]
        recovered_rows: list[int] = []
        for row_index in range(first_header - 1, table_min_row - 1, -1):
            if not self._row_has_header_text(grid, row_index, data_cols):
                break
            recovered_rows.append(row_index)

        return sorted(set([*recovered_rows, *header_rows]))

    def _row_has_header_text(self, grid: RawCellGrid, row_index: int, data_cols: list[int]) -> bool:
        has_text = False
        for col_index in data_cols:
            cell = self._cell_at(grid, row_index, col_index)
            value = cell.value if cell else None
            if value in (None, ""):
                continue
            if isinstance(value, (int, float)):
                return False
            text = self._normalize_name(value)
            if text:
                has_text = True
        return has_text

    def _region_min_row(self, region: str) -> int:
        match = re.match(r"[A-Z]+(\d+)", region.upper())
        return int(match.group(1)) if match else 1

    def _row_header_name(self, grid: RawCellGrid, header_rows: list[int], col_index: int) -> str:
        for row_index in reversed(header_rows):
            cell = self._cell_at(grid, row_index, col_index)
            if cell and cell.value not in (None, ""):
                return self._normalize_name(cell.value)
        return self._column_letter(col_index)

    def _value_header_name(
        self,
        grid: RawCellGrid,
        header_rows: list[int],
        col_index: int,
        inherited_group_rows: set[int],
    ) -> str:
        parts = []
        for row_index in header_rows:
            cell = (
                self._nearest_header_cell(grid, row_index, col_index)
                if row_index in inherited_group_rows
                else self._cell_at(grid, row_index, col_index)
            )
            if cell and cell.value not in (None, ""):
                value = self._normalize_name(cell.value)
                if value and value not in parts:
                    parts.append(value)
        return "_".join(parts) or self._column_letter(col_index)

    def _nearest_header_cell(self, grid: RawCellGrid, row_index: int, col_index: int) -> RawCell | None:
        exact = self._cell_at(grid, row_index, col_index)
        if exact and exact.value not in (None, ""):
            return exact

        current = col_index - 1
        while current >= 1:
            candidate = self._cell_at(grid, row_index, current)
            if candidate and candidate.value not in (None, ""):
                return candidate
            current -= 1
        return None

    def _dedupe_names(self, names: list[str]) -> list[str]:
        seen: dict[str, int] = {}
        result = []
        for name in names:
            base = name or "column"
            count = seen.get(base, 0)
            seen[base] = count + 1
            result.append(base if count == 0 else f"{base}_{count + 1}")
        return result

    def _cell_at(self, grid: RawCellGrid, row: int, col: int) -> RawCell | None:
        for cell in grid.cells:
            if cell.row == row and cell.col == col:
                return cell
        return None

    def _cell_extract_value(self, cell: RawCell | None):
        if cell is None:
            return None
        value = cell.display_value if cell.display_value is not None else cell.value
        if isinstance(value, str) and isinstance(cell.value, (int, float)):
            normalized = value.replace(",", "").strip()
            try:
                parsed = float(normalized)
            except ValueError:
                return value
            return int(parsed) if parsed.is_integer() else parsed
        return value

    def _normalize_name(self, value: object) -> str:
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        text = str(value).replace("\u3000", " ")
        text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"[^\w\u4e00-\u9fff]+", "_", text).strip("_")
        return re.sub(r"_+", "_", text)

    def _column_index(self, letter: str) -> int:
        result = 0
        for char in letter.upper():
            if not ("A" <= char <= "Z"):
                raise ValueError(f"Invalid column letter: {letter}")
            result = result * 26 + ord(char) - ord("A") + 1
        return result

    def _column_letter(self, col: int) -> str:
        letters = ""
        while col:
            col, remainder = divmod(col - 1, 26)
            letters = chr(65 + remainder) + letters
        return letters

    def _address(self, row: int, col: int) -> str:
        return f"{self._column_letter(col)}{row}"
