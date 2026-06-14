from openpyxl import Workbook

from app.services.excel_cell_grid import RawCellGridExtractor
from app.services.excel_table_block_detector import TableBlockDetector


def test_table_block_detector_splits_layout_blocks_without_domain_words(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Blocks"
    sheet["A1"] = "First title"
    sheet["A2"] = "Name"
    sheet["B2"] = "Value"
    sheet["A3"] = "Alpha"
    sheet["B3"] = 12
    sheet["A7"] = "Second title"
    sheet["A8"] = "Group"
    sheet["B8"] = "Amount"
    sheet["A9"] = "Beta"
    sheet["B9"] = 20

    path = tmp_path / "blocks.xlsx"
    workbook.save(path)
    grid = RawCellGridExtractor().extract(str(path))[0]

    blocks = TableBlockDetector().detect(grid)

    assert [block.region for block in blocks] == ["A1:B3", "A7:B9"]
    assert [block.non_empty_cell_count for block in blocks] == [5, 5]
    assert all(block.confidence >= 0.6 for block in blocks)


def test_table_block_detector_keeps_single_spacer_row_inside_complex_table(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Complex"
    sheet["C5"] = 2023
    sheet["E5"] = 2024
    sheet["C6"] = "Measure A"
    sheet["D6"] = "Measure B"
    sheet["E6"] = "Measure A"
    sheet["F6"] = "Measure B"
    sheet["A8"] = "Alpha"
    sheet["B8"] = "Alpha label"
    sheet["C8"] = 100
    sheet["D8"] = 0.2
    sheet["E8"] = 120
    sheet["F8"] = 0.3

    path = tmp_path / "complex.xlsx"
    workbook.save(path)
    grid = RawCellGridExtractor().extract(str(path))[0]

    blocks = TableBlockDetector(max_blank_rows_inside_block=1).detect(grid)

    assert [block.region for block in blocks] == ["A5:F8"]
