from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TableStructurePlan(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    table_region: str = Field(alias="tableRegion")
    title_rows: list[int] = Field(default_factory=list, alias="titleRows")
    unit_cells: list[str] = Field(default_factory=list, alias="unitCells")
    header_rows: list[int] = Field(alias="headerRows")
    data_start_row: int = Field(alias="dataStartRow")
    data_end_row: int | None = Field(default=None, alias="dataEndRow")
    row_header_columns: list[str] = Field(default_factory=list, alias="rowHeaderColumns")
    value_columns: list[str] = Field(default_factory=list, alias="valueColumns")
    category_rows: list[int] = Field(default_factory=list, alias="categoryRows")
    orientation: Literal["wide_table", "wide_year_table", "long_table", "unknown"] = "unknown"
    confidence: float = Field(ge=0, le=1)
    source: Literal["template", "vlm", "manual"] = "vlm"
