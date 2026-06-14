from __future__ import annotations

from dataclasses import dataclass

from app.services.excel_cell_grid import RawCell, RawCellGrid


@dataclass(frozen=True)
class TableBlock:
    min_row: int
    max_row: int
    min_col: int
    max_col: int
    non_empty_cell_count: int
    density: float
    confidence: float
    reasons: list[str]

    @property
    def region(self) -> str:
        return (
            f"{self._column_letter(self.min_col)}{self.min_row}:"
            f"{self._column_letter(self.max_col)}{self.max_row}"
        )

    def _column_letter(self, col: int) -> str:
        letters = ""
        while col:
            col, remainder = divmod(col - 1, 26)
            letters = chr(65 + remainder) + letters
        return letters


class TableBlockDetector:
    """Find candidate table blocks from 2D layout signals, without semantic labels."""

    def __init__(self, max_blank_rows_inside_block: int = 1, max_blank_cols_inside_block: int = 1) -> None:
        self.max_blank_rows_inside_block = max_blank_rows_inside_block
        self.max_blank_cols_inside_block = max_blank_cols_inside_block

    def detect(self, grid: RawCellGrid) -> list[TableBlock]:
        value_cells = [cell for cell in grid.cells if self._has_value(cell)]
        if not value_cells:
            return []

        row_segments = self._segments(
            sorted({cell.row for cell in value_cells}),
            self.max_blank_rows_inside_block,
        )
        blocks: list[TableBlock] = []
        for min_row, max_row in row_segments:
            row_cells = [cell for cell in value_cells if min_row <= cell.row <= max_row]
            col_segments = self._segments(
                sorted({cell.col for cell in row_cells}),
                self.max_blank_cols_inside_block,
            )
            for min_col, max_col in col_segments:
                block_cells = [
                    cell
                    for cell in row_cells
                    if min_col <= cell.col <= max_col
                ]
                block = self._make_block(min_row, max_row, min_col, max_col, block_cells)
                if block is not None:
                    blocks.append(block)

        return sorted(blocks, key=lambda block: (block.min_row, block.min_col))

    def _make_block(
        self,
        min_row: int,
        max_row: int,
        min_col: int,
        max_col: int,
        cells: list[RawCell],
    ) -> TableBlock | None:
        if len(cells) < 2:
            return None
        height = max_row - min_row + 1
        width = max_col - min_col + 1
        area = height * width
        density = len(cells) / area if area else 0
        confidence = 0.45
        reasons = ["layout_connected_cells"]
        if height >= 2:
            confidence += 0.1
            reasons.append("multiple_rows")
        if width >= 2:
            confidence += 0.1
            reasons.append("multiple_columns")
        if density >= 0.35:
            confidence += 0.15
            reasons.append("dense_region")
        if self._has_type_transition(cells):
            confidence += 0.1
            reasons.append("mixed_value_types")
        return TableBlock(
            min_row=min_row,
            max_row=max_row,
            min_col=min_col,
            max_col=max_col,
            non_empty_cell_count=len(cells),
            density=density,
            confidence=min(confidence, 0.95),
            reasons=reasons,
        )

    def _segments(self, indexes: list[int], allowed_gap: int) -> list[tuple[int, int]]:
        if not indexes:
            return []
        segments: list[tuple[int, int]] = []
        start = indexes[0]
        previous = indexes[0]
        for index in indexes[1:]:
            blank_gap = index - previous - 1
            if blank_gap > allowed_gap:
                segments.append((start, previous))
                start = index
            previous = index
        segments.append((start, previous))
        return segments

    def _has_type_transition(self, cells: list[RawCell]) -> bool:
        has_text = any(isinstance(cell.value, str) and cell.value.strip() for cell in cells)
        has_number = any(isinstance(cell.value, (int, float)) for cell in cells)
        return has_text and has_number

    def _has_value(self, cell: RawCell) -> bool:
        return cell.value is not None and bool(str(cell.value).strip())
