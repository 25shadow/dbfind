from openpyxl import Workbook

from app.services.excel_cell_grid import RawCellGridExtractor
from app.services.sheet_renderer import SheetRenderer


def test_sheet_renderer_outputs_coordinate_png_and_summary(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Visual"
    sheet["A1"] = "Title"
    sheet["A1"].font = sheet["A1"].font.copy(bold=True)
    sheet["A2"] = "Name"
    sheet["B2"] = 2024
    sheet["A3"] = "Alpha"
    sheet["B3"] = 12.5

    path = tmp_path / "visual.xlsx"
    workbook.save(path)
    grid = RawCellGridExtractor().extract(str(path))[0]

    rendering = SheetRenderer().render(grid)

    assert rendering.region == "A1:B3"
    assert rendering.png_base64.startswith("iVBOR")
    assert "data-address=\"A1\"" in rendering.html
    assert {"address": "B3", "row": 3, "col": "B", "valuePreview": "12.5", "valueType": "float", "bold": False, "filled": False, "mergedRange": None} in rendering.grid_summary
