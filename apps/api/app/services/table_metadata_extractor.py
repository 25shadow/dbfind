import re


class TableMetadataExtractor:
    def extract_from_grid_plan(self, grid, plan) -> dict[str, str | None]:
        blocks = []
        for row_index in sorted(set(plan.title_rows)):
            row_cells = [
                cell
                for cell in grid.cells
                if cell.row == row_index and cell.value not in (None, "")
            ]
            if not row_cells:
                continue
            row_cells.sort(key=lambda cell: cell.col)
            blocks.append(
                {
                    "region": f"{row_cells[0].address}:{row_cells[-1].address}",
                    "text": " ".join(str(cell.value) for cell in row_cells),
                    "cells": [cell.address for cell in row_cells],
                }
            )

        unit_rows = set()
        for address in plan.unit_cells:
            cell = self._grid_cell_by_address(grid, address)
            if cell and cell.value not in (None, ""):
                unit_rows.add(cell.row)
        for row_index in sorted(unit_rows):
            row_cells = [
                cell
                for cell in grid.cells
                if cell.row == row_index and cell.value not in (None, "")
            ]
            if not row_cells:
                continue
            row_cells.sort(key=lambda cell: cell.col)
            blocks.append(
                {
                    "region": f"{row_cells[0].address}:{row_cells[-1].address}",
                    "text": " ".join(str(cell.value) for cell in row_cells),
                    "cells": [cell.address for cell in row_cells],
                }
            )

        return self.extract(blocks)

    def extract(self, raw_content_blocks: list[dict]) -> dict[str, str | None]:
        texts = [
            self._normalize(str(block.get("text") or ""))
            for block in raw_content_blocks
            if self._normalize(str(block.get("text") or ""))
        ]
        unit = next((text for text in texts if self._is_unit_or_base(text)), None)
        title_candidates = [text for text in texts if text != unit]

        title = title_candidates[0] if title_candidates else None
        subtitle = None
        for text in title_candidates[1:]:
            if self._looks_english(text):
                subtitle = text
                break
        if subtitle is None and len(title_candidates) > 1:
            subtitle = title_candidates[1]

        return {
            "title": title,
            "subtitle": subtitle,
            "unit": unit,
        }

    def _is_unit_or_base(self, text: str) -> bool:
        normalized = text.lower()
        return (
            "单位" in text
            or "unit" in normalized
            or "=100" in normalized
            or bool(re.search(r"\([^)]*(yuan|percent|%)", normalized))
        )

    def _looks_english(self, text: str) -> bool:
        letters = re.findall(r"[A-Za-z]", text)
        chinese = re.findall(r"[\u4e00-\u9fff]", text)
        return len(letters) > 0 and len(letters) >= len(chinese)

    def _grid_cell_by_address(self, grid, address: str):
        match = re.fullmatch(r"([A-Za-z]+)(\d+)", address.strip())
        if not match:
            return None
        col = 0
        for char in match.group(1).upper():
            col = col * 26 + ord(char) - ord("A") + 1
        row = int(match.group(2))
        for cell in grid.cells:
            if cell.row == row and cell.col == col:
                return cell
        return None

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", text.replace("\u3000", " ")).strip()
