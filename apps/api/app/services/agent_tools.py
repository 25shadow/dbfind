from __future__ import annotations

import json
from typing import Any


def create_excel_agent_tools() -> list[Any]:
    from agents import function_tool

    @function_tool
    def query_excel_data(scope: str, question: str) -> str:
        """Plan a read-only Excel data query.

        This tool is for SELECT-style lookup, filtering, sorting, grouping,
        aggregation, and result export. It must not modify source files.
        """
        return _json(
            {
                "tool": "query",
                "scope": scope,
                "question": question,
                "safety": "read_only",
                "requiresConfirmation": False,
            }
        )

    @function_tool
    def transform_dataframe(scope: str, operations: list[str]) -> str:
        """Plan deterministic DataFrame transformations.

        Use pandas-backed generic operations for cleaning, filtering, type
        conversion, numeric formatting, derived columns, joins, appends, and
        reshaping. Supported operation types include filter_in, select_columns,
        sort_values, round, eval_expression, query, rename_columns,
        drop_duplicates, dropna, fillna, astype, and groupby_agg. Cross-row
        comparisons should usually be returned by the query step as SQL result
        columns before writing a workbook.
        """
        return _json(
            {
                "tool": "dataframe_transform",
                "scope": scope,
                "operations": operations,
                "safety": "preview_required",
                "requiresConfirmation": True,
            }
        )

    @function_tool
    def write_workbook(output_mode: str, sheet_name: str) -> str:
        """Plan writing generated data to a new Sheet or workbook.

        Source files must not be overwritten. Generated files are written under
        the configured generated/export workspace.
        """
        return _json(
            {
                "tool": "workbook_writer",
                "outputMode": output_mode,
                "sheetName": sheet_name,
                "safety": "generated_output_only",
                "requiresConfirmation": True,
            }
        )

    @function_tool
    def style_workbook(styles: list[str]) -> str:
        """Plan workbook styling.

        Use for titles, headers, widths, frozen panes, filters, number formats,
        Excel tables, borders, colors, conditional formatting, and charts.
        """
        return _json(
            {
                "tool": "workbook_style",
                "styles": styles,
                "safety": "preview_required",
                "requiresConfirmation": True,
            }
        )

    return [query_excel_data, transform_dataframe, write_workbook, style_workbook]


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)
