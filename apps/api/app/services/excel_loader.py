from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class LoadedSheet:
    name: str
    dataframe: pd.DataFrame
    title: str | None = None
    subtitle: str | None = None
    unit: str | None = None


class ExcelLoader:
    """CSV parser. Excel files are handled by the structure parsing pipeline."""

    def load(self, path: str) -> list[LoadedSheet]:
        file_path = Path(path)
        extension = file_path.suffix.lower()

        if extension == ".csv":
            dataframe = pd.read_csv(file_path)
            return [LoadedSheet(name=file_path.stem, dataframe=self._normalize_dataframe(dataframe))]

        if extension in {".et", ".ods", ".xls", ".xlsb", ".xlsm", ".xlsx"}:
            raise ValueError("Excel 文件请使用结构解析流程")

        raise ValueError("只支持 .xlsx、.xls、.xlsm、.xlsb、.et、.ods 和 .csv 文件")

    def _normalize_dataframe(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        normalized = dataframe.dropna(axis=1, how="all").copy().astype(object)
        for column in normalized.columns:
            normalized[column] = pd.Series(
                [self._normalize_cell_value(value) for value in normalized[column].tolist()],
                index=normalized.index,
                dtype=object,
            )
        normalized.columns = [str(column).strip() for column in normalized.columns]
        return normalized

    def _normalize_cell_value(self, value):
        if pd.isna(value):
            return None
        if isinstance(value, str):
            return value.strip()
        return value
