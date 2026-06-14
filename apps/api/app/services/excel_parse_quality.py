from __future__ import annotations

from dataclasses import dataclass
from numbers import Number
import re

import pandas as pd


@dataclass(frozen=True)
class ExcelParseQuality:
    confidence: str
    issues: list[str]

    @property
    def is_importable(self) -> bool:
        return self.confidence in {"high", "medium"}


class ExcelParseQualityEvaluator:
    def evaluate(self, dataframe: pd.DataFrame) -> ExcelParseQuality:
        issues: list[str] = []
        if len(dataframe.index) == 0 or len(dataframe.columns) == 0:
            return ExcelParseQuality("low", ["empty_table"])

        if len(dataframe.index) <= 1 and not self._has_numeric_data(dataframe):
            issues.append("only_one_non_numeric_row")

        duplicate_ratio = self._dominant_duplicate_column_base_ratio(dataframe.columns)
        if len(dataframe.columns) >= 4 and duplicate_ratio >= 0.5:
            issues.append("repeated_title_like_columns")

        if self._looks_like_unit_only_rows(dataframe):
            issues.append("unit_or_header_rows_without_data")

        if issues:
            return ExcelParseQuality("low", issues)
        if len(dataframe.index) <= 2:
            return ExcelParseQuality("medium", ["small_table"])
        return ExcelParseQuality("high", [])

    def _has_numeric_data(self, dataframe: pd.DataFrame) -> bool:
        for value in dataframe.to_numpy().flatten():
            if isinstance(value, Number) and not pd.isna(value):
                return True
        return False

    def _dominant_duplicate_column_base_ratio(self, columns) -> float:
        bases: dict[str, int] = {}
        for column in columns:
            base = re.sub(r"_\d+$", "", str(column))
            if base == "column":
                continue
            bases[base] = bases.get(base, 0) + 1
        if not bases:
            return 0
        return max(bases.values()) / max(1, len(list(columns)))

    def _looks_like_unit_only_rows(self, dataframe: pd.DataFrame) -> bool:
        if len(dataframe.index) > 2:
            return False
        if self._has_numeric_data(dataframe):
            return False
        text = " ".join(
            str(value).strip().lower()
            for value in dataframe.to_numpy().flatten()
            if not pd.isna(value) and str(value).strip()
        )
        if not text:
            return True
        values = [
            str(value).strip()
            for value in dataframe.to_numpy().flatten()
            if not pd.isna(value) and str(value).strip()
        ]
        return bool(values) and all(len(value) <= 40 for value in values)
