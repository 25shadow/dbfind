from __future__ import annotations

import base64
from io import BytesIO
from dataclasses import dataclass
from html import escape

from PIL import Image, ImageDraw, ImageFont

from app.services.excel_cell_grid import RawCell, RawCellGrid
from app.services.excel_table_block_detector import TableBlock


@dataclass(frozen=True)
class SheetRendering:
    sheet_name: str
    region: str
    html: str
    png_base64: str
    grid_summary: list[dict[str, object]]


class SheetRenderer:
    """Render a spreadsheet region with stable row/column coordinates for VLM planning."""

    def render(self, grid: RawCellGrid, block: TableBlock | None = None) -> SheetRendering:
        min_row, max_row, min_col, max_col = self._bounds(grid, block)
        cell_map = {(cell.row, cell.col): cell for cell in grid.cells}
        rows = []
        summary = []

        for row_index in range(min_row, max_row + 1):
            cells = [f'<th class="row-header">{row_index}</th>']
            for col_index in range(min_col, max_col + 1):
                cell = cell_map.get((row_index, col_index))
                value = "" if cell is None or cell.value is None else str(cell.value)
                classes = ["cell"]
                if cell and cell.bold:
                    classes.append("bold")
                if cell and cell.fill_color:
                    classes.append("filled")
                if cell and cell.merged_range:
                    classes.append("merged")
                cells.append(
                    '<td data-address="{address}" class="{classes}">{value}</td>'.format(
                        address=self._address(row_index, col_index),
                        classes=" ".join(classes),
                        value=escape(value),
                    )
                )
                if cell and cell.value not in (None, ""):
                    summary.append(self._summary_cell(cell))
            rows.append("<tr>" + "".join(cells) + "</tr>")

        header = "".join(
            f'<th class="col-header">{self._column_letter(col_index)}</th>'
            for col_index in range(min_col, max_col + 1)
        )
        html = self._document(f'<tr><th class="corner"></th>{header}</tr>' + "".join(rows))
        png_base64 = self._png_base64(grid, min_row, max_row, min_col, max_col)
        return SheetRendering(
            sheet_name=grid.sheet_name,
            region=f"{self._column_letter(min_col)}{min_row}:{self._column_letter(max_col)}{max_row}",
            html=html,
            png_base64=png_base64,
            grid_summary=summary,
        )

    def _bounds(self, grid: RawCellGrid, block: TableBlock | None) -> tuple[int, int, int, int]:
        if block is not None:
            return block.min_row, block.max_row, block.min_col, block.max_col
        rows = [cell.row for cell in grid.cells]
        cols = [cell.col for cell in grid.cells]
        if not rows or not cols:
            return 1, max(grid.max_row, 1), 1, max(grid.max_col, 1)
        return min(rows), max(rows), min(cols), max(cols)

    def _summary_cell(self, cell: RawCell) -> dict[str, object]:
        return {
            "address": cell.address,
            "row": cell.row,
            "col": self._column_letter(cell.col),
            "valuePreview": str(cell.value)[:80],
            "valueType": type(cell.value).__name__,
            "bold": cell.bold,
            "filled": bool(cell.fill_color),
            "mergedRange": cell.merged_range,
        }

    def _document(self, rows: str) -> str:
        return (
            "<!doctype html><html><head><meta charset=\"utf-8\">"
            "<style>"
            "body{margin:0;background:#fff;font-family:Arial,sans-serif;color:#111827;}"
            "table{border-collapse:collapse;font-size:12px;line-height:1.25;}"
            "th,td{border:1px solid #d1d5db;min-width:72px;height:26px;padding:3px 6px;}"
            ".corner,.row-header,.col-header{background:#f3f4f6;color:#374151;font-weight:600;}"
            ".row-header{min-width:38px;text-align:right;}"
            ".cell{background:#fff;vertical-align:middle;}"
            ".bold{font-weight:700;}"
            ".filled{background:#e5f0ff;}"
            ".merged{outline:2px solid #60a5fa;outline-offset:-2px;}"
            "</style></head><body><table>"
            f"{rows}"
            "</table></body></html>"
        )

    def _png_base64(
        self,
        grid: RawCellGrid,
        min_row: int,
        max_row: int,
        min_col: int,
        max_col: int,
    ) -> str:
        cell_width = 132
        cell_height = 34
        row_header_width = 48
        col_header_height = 30
        width = row_header_width + (max_col - min_col + 1) * cell_width
        height = col_header_height + (max_row - min_row + 1) * cell_height
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()
        cell_map = {(cell.row, cell.col): cell for cell in grid.cells}

        draw.rectangle([0, 0, width - 1, height - 1], outline="#d1d5db", fill="#ffffff")
        for col_index in range(min_col, max_col + 1):
            x = row_header_width + (col_index - min_col) * cell_width
            draw.rectangle([x, 0, x + cell_width, col_header_height], fill="#f3f4f6", outline="#d1d5db")
            draw.text((x + 6, 8), self._column_letter(col_index), fill="#374151", font=font)

        for row_index in range(min_row, max_row + 1):
            y = col_header_height + (row_index - min_row) * cell_height
            draw.rectangle([0, y, row_header_width, y + cell_height], fill="#f3f4f6", outline="#d1d5db")
            draw.text((6, y + 10), str(row_index), fill="#374151", font=font)
            for col_index in range(min_col, max_col + 1):
                x = row_header_width + (col_index - min_col) * cell_width
                cell = cell_map.get((row_index, col_index))
                fill = "#e5f0ff" if cell and cell.fill_color else "#ffffff"
                draw.rectangle([x, y, x + cell_width, y + cell_height], fill=fill, outline="#d1d5db")
                if cell and cell.merged_range:
                    draw.rectangle([x + 1, y + 1, x + cell_width - 1, y + cell_height - 1], outline="#60a5fa", width=2)
                if cell and cell.value not in (None, ""):
                    draw.text((x + 6, y + 10), self._clip_text(str(cell.value)), fill="#111827", font=font)

        output = BytesIO()
        image.save(output, format="PNG")
        return base64.b64encode(output.getvalue()).decode("ascii")

    def _clip_text(self, text: str) -> str:
        return text if len(text) <= 18 else f"{text[:17]}..."

    def _address(self, row: int, col: int) -> str:
        return f"{self._column_letter(col)}{row}"

    def _column_letter(self, col: int) -> str:
        letters = ""
        while col:
            col, remainder = divmod(col - 1, 26)
            letters = chr(65 + remainder) + letters
        return letters
