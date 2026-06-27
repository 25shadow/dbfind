from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class WorkbookDesignDefaults:
    freeze_header: bool = True
    autofilter: bool = True
    header_fill: str = "E8F1FF"
    as_table: bool = False
    table_style: str = "Table Style Medium 2"


WORKBOOK_DESIGN_DEFAULTS = WorkbookDesignDefaults()


@dataclass(frozen=True)
class WorkbookDesign:
    freeze_header: bool = WORKBOOK_DESIGN_DEFAULTS.freeze_header
    autofilter: bool = WORKBOOK_DESIGN_DEFAULTS.autofilter
    header_fill: str = WORKBOOK_DESIGN_DEFAULTS.header_fill
    number_formats: dict[str, str] = field(default_factory=dict)
    as_table: bool = WORKBOOK_DESIGN_DEFAULTS.as_table
    table_style: str = WORKBOOK_DESIGN_DEFAULTS.table_style
    conditional_formats: list[dict[str, Any]] = field(default_factory=list)
    charts: list[dict[str, Any]] = field(default_factory=list)


class DataFrameOperationEngine:
    def apply(self, dataframe: pd.DataFrame, operations: list[dict[str, Any]]) -> pd.DataFrame:
        result = dataframe.copy()
        for operation in operations:
            operation_type = operation.get("type")
            if operation_type == "filter_in":
                result = self._filter_in(result, operation)
            elif operation_type == "select_columns":
                result = self._select_columns(result, operation)
            elif operation_type == "sort_values":
                result = self._sort_values(result, operation)
            elif operation_type == "round":
                result = self._round(result, operation)
            elif operation_type == "eval_expression":
                result = self._eval_expression(result, operation)
            elif operation_type == "query":
                result = self._query(result, operation)
            elif operation_type == "rename_columns":
                result = self._rename_columns(result, operation)
            elif operation_type == "drop_duplicates":
                result = self._drop_duplicates(result, operation)
            elif operation_type == "dropna":
                result = self._dropna(result, operation)
            elif operation_type == "fillna":
                result = self._fillna(result, operation)
            elif operation_type == "astype":
                result = self._astype(result, operation)
            elif operation_type == "groupby_agg":
                result = self._groupby_agg(result, operation)
            else:
                raise ValueError(f"不支持的 DataFrame 操作: {operation_type}")
        return result.reset_index(drop=True)

    def _filter_in(self, dataframe: pd.DataFrame, operation: dict[str, Any]) -> pd.DataFrame:
        column = self._required_column(dataframe, operation.get("column"))
        values = operation.get("values")
        if not isinstance(values, list) or not values:
            raise ValueError("filter_in 操作需要非空 values")
        return dataframe[dataframe[column].isin(values)]

    def _select_columns(self, dataframe: pd.DataFrame, operation: dict[str, Any]) -> pd.DataFrame:
        columns = operation.get("columns")
        if not isinstance(columns, list) or not columns:
            raise ValueError("select_columns 操作需要非空 columns")
        missing = [column for column in columns if column not in dataframe.columns]
        if missing:
            raise ValueError(f"字段不存在: {', '.join(missing)}")
        return dataframe[columns]

    def _sort_values(self, dataframe: pd.DataFrame, operation: dict[str, Any]) -> pd.DataFrame:
        columns = operation.get("by")
        if isinstance(columns, str):
            columns = [columns]
        if not isinstance(columns, list) or not columns:
            raise ValueError("sort_values 操作需要 by")
        missing = [column for column in columns if column not in dataframe.columns]
        if missing:
            raise ValueError(f"字段不存在: {', '.join(missing)}")
        ascending = operation.get("ascending", True)
        return dataframe.sort_values(by=columns, ascending=ascending)

    def _round(self, dataframe: pd.DataFrame, operation: dict[str, Any]) -> pd.DataFrame:
        columns = operation.get("columns")
        if not isinstance(columns, list) or not columns:
            raise ValueError("round 操作需要非空 columns")
        decimals = operation.get("decimals", 0)
        if not isinstance(decimals, int) or decimals < 0:
            raise ValueError("round 操作的 decimals 必须是非负整数")
        result = dataframe.copy()
        for column in columns:
            self._required_column(result, column)
            result[column] = pd.to_numeric(result[column], errors="coerce").round(decimals)
        return result

    def _eval_expression(self, dataframe: pd.DataFrame, operation: dict[str, Any]) -> pd.DataFrame:
        expression = operation.get("expression")
        if not isinstance(expression, str) or not expression.strip():
            raise ValueError("eval_expression 操作需要 expression")
        try:
            return dataframe.eval(expression.strip(), inplace=False)
        except Exception as exc:
            raise ValueError(f"pandas 表达式执行失败: {exc}") from exc

    def _query(self, dataframe: pd.DataFrame, operation: dict[str, Any]) -> pd.DataFrame:
        expression = operation.get("expression")
        if not isinstance(expression, str) or not expression.strip():
            raise ValueError("query 操作需要 expression")
        try:
            return dataframe.query(expression.strip())
        except Exception as exc:
            raise ValueError(f"pandas 查询表达式执行失败: {exc}") from exc

    def _rename_columns(self, dataframe: pd.DataFrame, operation: dict[str, Any]) -> pd.DataFrame:
        columns = operation.get("columns")
        if not isinstance(columns, dict) or not columns:
            raise ValueError("rename_columns 操作需要 columns")
        mapping = {str(source): str(target) for source, target in columns.items()}
        missing = [column for column in mapping if column not in dataframe.columns]
        if missing:
            raise ValueError(f"字段不存在: {', '.join(missing)}")
        return dataframe.rename(columns=mapping)

    def _drop_duplicates(self, dataframe: pd.DataFrame, operation: dict[str, Any]) -> pd.DataFrame:
        subset = self._optional_columns(dataframe, operation.get("subset"))
        keep = operation.get("keep", "first")
        if keep not in {"first", "last", False}:
            raise ValueError("drop_duplicates 操作的 keep 必须是 first、last 或 false")
        return dataframe.drop_duplicates(subset=subset, keep=keep)

    def _dropna(self, dataframe: pd.DataFrame, operation: dict[str, Any]) -> pd.DataFrame:
        subset = self._optional_columns(dataframe, operation.get("subset"))
        how = operation.get("how", "any")
        if how not in {"any", "all"}:
            raise ValueError("dropna 操作的 how 必须是 any 或 all")
        return dataframe.dropna(subset=subset, how=how)

    def _fillna(self, dataframe: pd.DataFrame, operation: dict[str, Any]) -> pd.DataFrame:
        values = operation.get("values", operation.get("value"))
        if values is None:
            raise ValueError("fillna 操作需要 values 或 value")
        if isinstance(values, dict):
            missing = [column for column in values if column not in dataframe.columns]
            if missing:
                raise ValueError(f"字段不存在: {', '.join(missing)}")
        return dataframe.fillna(value=values)

    def _astype(self, dataframe: pd.DataFrame, operation: dict[str, Any]) -> pd.DataFrame:
        columns = operation.get("columns")
        if not isinstance(columns, dict) or not columns:
            raise ValueError("astype 操作需要 columns")
        mapping = {str(column): str(dtype) for column, dtype in columns.items()}
        missing = [column for column in mapping if column not in dataframe.columns]
        if missing:
            raise ValueError(f"字段不存在: {', '.join(missing)}")
        try:
            return dataframe.astype(mapping)
        except Exception as exc:
            raise ValueError(f"pandas 类型转换失败: {exc}") from exc

    def _groupby_agg(self, dataframe: pd.DataFrame, operation: dict[str, Any]) -> pd.DataFrame:
        by = operation.get("by")
        if isinstance(by, str):
            by = [by]
        if not isinstance(by, list) or not by:
            raise ValueError("groupby_agg 操作需要 by")
        group_columns = [self._required_column(dataframe, column) for column in by]
        aggregations = operation.get("aggregations")
        if not isinstance(aggregations, dict) or not aggregations:
            raise ValueError("groupby_agg 操作需要 aggregations")
        named_aggregations = {}
        for column, functions in aggregations.items():
            source_column = self._required_column(dataframe, column)
            function_list = functions if isinstance(functions, list) else [functions]
            for function in function_list:
                if not isinstance(function, str) or not function:
                    raise ValueError("groupby_agg 聚合函数必须是字符串")
                named_aggregations[f"{source_column}_{function}"] = (source_column, function)
        return dataframe.groupby(group_columns, dropna=False).agg(**named_aggregations).reset_index()

    def _required_column(self, dataframe: pd.DataFrame, column: Any) -> str:
        if not isinstance(column, str) or not column:
            raise ValueError("操作需要有效字段名")
        if column not in dataframe.columns:
            raise ValueError(f"字段不存在: {column}")
        return column

    def _optional_columns(self, dataframe: pd.DataFrame, columns: Any) -> list[str] | None:
        if columns is None:
            return None
        if isinstance(columns, str):
            columns = [columns]
        if not isinstance(columns, list) or not columns:
            raise ValueError("操作字段列表必须是非空数组")
        return [self._required_column(dataframe, column) for column in columns]


class WorkbookOperationEngine:
    def write_workbook(
        self,
        output_path: Path,
        sheets: list[tuple[str, pd.DataFrame]],
        design: WorkbookDesign | None = None,
    ) -> None:
        if not sheets:
            raise ValueError("没有可写出的 Sheet")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_with_xlsxwriter(output_path, sheets, design or WorkbookDesign())

    def _write_with_xlsxwriter(
        self,
        output_path: Path,
        sheets: list[tuple[str, pd.DataFrame]],
        design: WorkbookDesign,
    ) -> None:
        import xlsxwriter

        with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
            workbook = writer.book
            header_format = workbook.add_format(
                {
                    "bold": True,
                    "bg_color": f"#{design.header_fill}",
                    "border": 1,
                }
            )
            normal_number_formats = {
                column: workbook.add_format({"num_format": number_format})
                for column, number_format in design.number_formats.items()
            }
            conditional_formats = self._build_conditional_formats(workbook, design.conditional_formats)
            charts = self._build_charts(design.charts)

            for sheet_name, dataframe in sheets:
                safe_name = self.safe_sheet_name(sheet_name)
                dataframe.to_excel(writer, sheet_name=safe_name, index=False, startrow=0)
                worksheet = writer.sheets[safe_name]
                rows, cols = dataframe.shape
                if rows == 0 and cols == 0:
                    continue

                worksheet.set_row(0, None, header_format)
                for index, column in enumerate(dataframe.columns):
                    worksheet.write(0, index, str(column), header_format)
                if design.freeze_header:
                    worksheet.freeze_panes(1, 0)
                if design.autofilter and not design.as_table and cols > 0 and rows >= 0:
                    worksheet.autofilter(0, 0, rows, cols - 1)
                if design.as_table and cols > 0:
                    worksheet.add_table(
                        0,
                        0,
                        rows,
                        cols - 1,
                        {
                            "style": design.table_style,
                            "columns": [{"header": str(column)} for column in dataframe.columns],
                        },
                    )
                for index, column in enumerate(dataframe.columns):
                    number_format = normal_number_formats.get(column)
                    if number_format is not None:
                        worksheet.set_column(index, index, None, number_format)

                worksheet.autofit()

                for conditional in conditional_formats:
                    column_index = self._column_index_by_name(dataframe, conditional["column"])
                    if column_index is None or rows == 0:
                        continue
                    cell_format = workbook.add_format(conditional["format"])
                    worksheet.conditional_format(
                        1,
                        column_index,
                        rows,
                        column_index,
                        {
                            "type": conditional["type"],
                            "criteria": conditional["criteria"],
                            "value": conditional["value"],
                            "format": cell_format,
                        },
                    )

                for chart_spec in charts:
                    if rows == 0:
                        continue
                    categories_column = self._column_index_by_name(
                        dataframe, chart_spec["categories_column"]
                    )
                    values_column = self._column_index_by_name(dataframe, chart_spec["values_column"])
                    if categories_column is None or values_column is None:
                        continue
                    chart = workbook.add_chart({"type": chart_spec["type"]})
                    chart.add_series(
                        {
                            "name": chart_spec.get("series_name") or chart_spec["values_column"],
                            "categories": [safe_name, 1, categories_column, rows, categories_column],
                            "values": [safe_name, 1, values_column, rows, values_column],
                        }
                    )
                    if chart_spec.get("title"):
                        chart.set_title({"name": chart_spec["title"]})
                    worksheet.insert_chart(chart_spec["position"], chart)

    def _build_conditional_formats(
        self,
        workbook: Any,
        formats: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            {
                "column": item["column"],
                "type": item.get("type", "cell"),
                "criteria": item.get("criteria", ">"),
                "value": item.get("value", 0),
                "format": item.get("format", {}),
            }
            for item in formats
            if isinstance(item, dict) and item.get("column") and isinstance(item.get("format"), dict)
        ]

    def _build_charts(self, charts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        supported_types = {"area", "bar", "column", "line", "pie", "scatter"}
        normalized = []
        for item in charts:
            if not isinstance(item, dict):
                continue
            chart_type = item.get("type", "column")
            categories_column = item.get("categoriesColumn") or item.get("categories_column")
            values_column = item.get("valuesColumn") or item.get("values_column")
            if chart_type not in supported_types:
                continue
            if not isinstance(categories_column, str) or not isinstance(values_column, str):
                continue
            normalized.append(
                {
                    "type": chart_type,
                    "title": item.get("title") if isinstance(item.get("title"), str) else None,
                    "series_name": (
                        item.get("seriesName") or item.get("series_name")
                        if isinstance(item.get("seriesName") or item.get("series_name"), str)
                        else None
                    ),
                    "categories_column": categories_column,
                    "values_column": values_column,
                    "position": item.get("position") if isinstance(item.get("position"), str) else "E2",
                }
            )
        return normalized

    def safe_sheet_name(self, name: str) -> str:
        safe = "".join("_" if char in r'[]:*?/\\' else char for char in name).strip()
        return (safe or "Sheet")[:31]

    def _column_index_by_name(self, dataframe: pd.DataFrame, column: str) -> int | None:
        try:
            return int(dataframe.columns.get_loc(column))
        except KeyError:
            return None
