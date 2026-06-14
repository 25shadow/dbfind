from __future__ import annotations

import json
import re

import httpx
from pydantic import ValidationError

from app.schemas.table_structure import TableStructurePlan
from app.services.excel_cell_grid import RawCellGrid
from app.services.settings_service import SettingsService
from app.services.sheet_renderer import SheetRendering


class VisionStructurePlanner:
    """Ask a vision-capable model for a coordinate-only table structure plan."""

    def availability_issue(self) -> str | None:
        settings = SettingsService().get()
        if not settings.vision_model:
            return "vlm_model_missing"
        if not settings.vision_api_key:
            return "vlm_api_key_missing"
        return None

    def plan(self, grid: RawCellGrid, rendering: SheetRendering) -> TableStructurePlan | None:
        settings = SettingsService().get()
        if self.availability_issue() is not None:
            return None

        url = f"{settings.vision_ai_base_url.rstrip('/')}{settings.vision_ai_chat_path}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.vision_api_key}",
        }
        request_body = {
            "model": settings.vision_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self._user_prompt(grid, rendering)},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{rendering.png_base64}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            "max_tokens": 1200,
        }

        with httpx.Client(timeout=60) as client:
            response = client.post(url, json=request_body, headers=headers)
            response.raise_for_status()
            data = response.json()

        content = self._extract_content(data)
        if not content:
            return None
        plan = self._parse_plan(content)
        plan.source = "vlm"
        return plan

    def _system_prompt(self) -> str:
        return (
            "You are a spreadsheet structure planner. Return only JSON. "
            "Your job is to identify spreadsheet structure from the image and coordinate summary. "
            "Do not extract, calculate, invent, or rewrite table data values. "
            "Return coordinates only: tableRegion, titleRows, unitCells, headerRows, dataStartRow, "
            "dataEndRow, rowHeaderColumns, valueColumns, categoryRows, orientation, confidence, source. "
            "tableRegion should cover the whole related sheet content block, including titles, headers, "
            "data rows, footnotes, notes, and remarks. dataStartRow/dataEndRow must cover only data rows. "
            "headerRows must include every row above dataStartRow that contributes column labels, including "
            "group headers, translated labels, bilingual labels, and wrapped header text. "
            "Use Excel coordinates from visible row and column headers. "
            "If uncertain, lower confidence instead of guessing."
        )

    def _user_prompt(self, grid: RawCellGrid, rendering: SheetRendering) -> str:
        return json.dumps(
            {
                "task": "Return a coordinate-only TableStructurePlan for this spreadsheet region.",
                "sheetName": grid.sheet_name,
                "renderedRegion": rendering.region,
                "maxRow": grid.max_row,
                "maxColumn": grid.max_col,
                "nonEmptyCellSummary": rendering.grid_summary[:240],
                "outputSchema": {
                    "tableRegion": "A1:D20",
                    "titleRows": [1],
                    "unitCells": ["D2"],
                    "headerRows": [3, 4],
                    "dataStartRow": 5,
                    "dataEndRow": 20,
                    "rowHeaderColumns": ["A"],
                    "valueColumns": ["B", "C", "D"],
                    "categoryRows": [],
                    "orientation": "wide_year_table",
                    "confidence": 0.0,
                    "source": "vlm",
                },
                "rules": [
                    "Do not drop non-empty rows below the data table; include them inside tableRegion.",
                    "Do not put note or remark rows into dataStartRow/dataEndRow unless they are real data rows.",
                    "Include all contiguous column-header rows above dataStartRow in headerRows, even when some rows are translated versions or wrapped text.",
                    "Do not choose only the English row or only the local-language row when both appear as headers.",
                    "orientation must be exactly one of: wide_table, wide_year_table, long_table, unknown.",
                    "Only return coordinates and confidence; do not transcribe table data.",
                ],
            },
            ensure_ascii=False,
        )

    def _extract_content(self, data: dict) -> str:
        choices = data.get("choices")
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        content = message.get("content") or choices[0].get("text") or ""
        return str(content).strip()

    def _parse_plan(self, content: str) -> TableStructurePlan:
        payload = self._json_payload(content)
        if payload is not None:
            self._normalize_orientation(payload)
            return TableStructurePlan.model_validate(payload)

        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            return TableStructurePlan.model_validate_json(content)
        payload = self._json_payload(match.group(0))
        if payload is not None:
            self._normalize_orientation(payload)
            return TableStructurePlan.model_validate(payload)
        return TableStructurePlan.model_validate_json(match.group(0))

    def _json_payload(self, content: str) -> dict | None:
        try:
            data = json.loads(content)
        except ValueError:
            return None
        return data if isinstance(data, dict) else None

    def _normalize_orientation(self, payload: dict) -> None:
        value = payload.get("orientation")
        if not isinstance(value, str):
            return
        allowed = ("wide_year_table", "wide_table", "long_table", "unknown")
        if value in allowed:
            return
        tokens = re.split(r"[\s|,/]+", value)
        for candidate in allowed:
            if candidate in tokens:
                payload["orientation"] = candidate
                return
