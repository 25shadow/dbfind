import pandas as pd

from app.services.excel_structure_detector import (
    ExcelSheetSignals,
    ExcelStructureDetector,
    MergedCellRange,
)


def test_detects_title_header_and_data_regions_for_year_matrix() -> None:
    dataframe = pd.DataFrame(
        [
            ["1-2 农业主要指标", None, None, None, None, None, None, None, None],
            ["指标", "单位", 2000.0, 2005.0, 2010.0, 2015.0, 2019.0, 2020.0, 2021.0],
            ["乡村户数", "万户", 1419.91, 1540.84, 1686.62, 1689.97, 1723.91, 1751.30, 1835.5],
        ]
    )

    structure = ExcelStructureDetector().detect(dataframe)

    assert structure.header_start == 1
    assert structure.header_end == 1
    assert structure.data_start == 2
    assert structure.title_rows == [0]
    assert structure.confidence == "high"
    assert "year_header_cells" in structure.reasons


def test_detects_grouped_two_row_header_continuation() -> None:
    dataframe = pd.DataFrame(
        [
            ["标题", None, None, None, None, None],
            ["指标", "单位", "2021", "分组表头", None, None],
            [None, None, None, "年份", "数值", "比例"],
            ["甲项目", "万吨", 12.3, 1997, 45.6, 27.0],
        ]
    )

    structure = ExcelStructureDetector().detect(dataframe)

    assert structure.header_start == 1
    assert structure.header_end == 2
    assert structure.data_start == 3
    assert structure.title_rows == [0]


def test_rejects_plain_data_rows_as_header() -> None:
    dataframe = pd.DataFrame(
        [
            ["乡村户数", "万户", 1419.91, 1540.84, 1686.62],
            ["农业总产值", "亿元", 1701.18, 2447.57, 3697.18],
        ]
    )

    structure = ExcelStructureDetector().detect(dataframe)

    assert structure.header_start is None
    assert structure.header_end is None
    assert structure.data_start == 0
    assert structure.confidence == "none"


def test_merged_title_signal_marks_title_row() -> None:
    dataframe = pd.DataFrame(
        [
            ["1-2 农业主要指标", None, None, None],
            ["指标", "单位", 2020.0, 2021.0],
            ["乡村户数", "万户", 1751.3, 1835.5],
        ]
    )
    signals = ExcelSheetSignals(
        merged_ranges=[MergedCellRange(start_row=0, end_row=0, start_col=0, end_col=3)]
    )

    structure = ExcelStructureDetector().detect(dataframe, signals=signals)

    assert structure.title_rows == [0]
    assert "merged_title_row" in structure.reasons


def test_styled_header_signal_can_promote_sparse_header() -> None:
    dataframe = pd.DataFrame(
        [
            ["地区", 2020.0, 2021.0],
            ["广州", 12.0, 14.0],
            ["深圳", 22.0, 25.0],
        ]
    )
    signals = ExcelSheetSignals(styled_rows={0})

    structure = ExcelStructureDetector().detect(dataframe, signals=signals)

    assert structure.header_start == 0
    assert structure.header_end == 0
    assert structure.data_start == 1
    assert "styled_header_row" in structure.reasons


def test_detects_multiple_table_regions_separated_by_blank_rows() -> None:
    dataframe = pd.DataFrame(
        [
            ["农业主要指标", None, None],
            ["指标", "单位", 2021.0],
            ["乡村户数", "万户", 1835.5],
            [None, None, None],
            ["行政区划", None, None],
            ["市别", "县", "乡"],
            ["全省", 76, 1120],
        ]
    )

    regions = ExcelStructureDetector().detect_regions(dataframe)

    assert [(region.header_start, region.data_start) for region in regions] == [(1, 2), (5, 6)]


def test_blank_row_after_header_stops_header_continuation_before_category_rows() -> None:
    dataframe = pd.DataFrame(
        [
            ["Report", None, None, None, None],
            ["Label", "Item", 2000.0, 2010.0, 2024.0],
            [None, None, None, None, None],
            ["Group A", "Group A label", None, None, None],
            ["Category", "Category label", None, None, None],
            ["Alpha", "Alpha label", 97.6, 96.5, 98.7],
        ]
    )

    structure = ExcelStructureDetector().detect(dataframe)

    assert structure.header_start == 1
    assert structure.header_end == 1
    assert structure.data_start == 2
