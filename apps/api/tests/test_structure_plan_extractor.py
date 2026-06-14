from openpyxl import Workbook

from app.schemas.table_structure import TableStructurePlan
from app.services.excel_cell_grid import RawCellGridExtractor
from app.services.structure_plan_extractor import StructurePlanExtractor


def test_structure_plan_extractor_expands_multi_row_headers_from_real_cells(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Complex"
    sheet["A1"] = "Report Title"
    sheet["C5"] = 2023
    sheet["E5"] = 2024
    sheet["C6"] = "Measure A"
    sheet["D6"] = "Measure B"
    sheet["E6"] = "Measure A"
    sheet["F6"] = "Measure B"
    sheet["C7"] = "Count"
    sheet["D7"] = "Ratio"
    sheet["E7"] = "Count"
    sheet["F7"] = "Ratio"
    sheet["A9"] = "Alpha"
    sheet["B9"] = "Alpha label"
    sheet["C9"] = 100
    sheet["D9"] = 0.2
    sheet["E9"] = 120
    sheet["F9"] = 0.3

    path = tmp_path / "complex.xlsx"
    workbook.save(path)
    grid = RawCellGridExtractor().extract(str(path))[0]
    plan = TableStructurePlan(
        tableRegion="A5:F9",
        titleRows=[1],
        headerRows=[5, 6, 7],
        dataStartRow=9,
        dataEndRow=9,
        rowHeaderColumns=["A", "B"],
        valueColumns=["C", "D", "E", "F"],
        orientation="wide_year_table",
        confidence=0.9,
        source="manual",
    )

    extracted = StructurePlanExtractor().extract(grid, plan)

    assert list(extracted.dataframe.columns) == [
        "A",
        "B",
        "2023_Measure_A_Count",
        "2023_Measure_B_Ratio",
        "2024_Measure_A_Count",
        "2024_Measure_B_Ratio",
    ]
    assert extracted.dataframe.iloc[0].to_dict() == {
        "A": "Alpha",
        "B": "Alpha label",
        "2023_Measure_A_Count": 100,
        "2023_Measure_B_Ratio": 0.2,
        "2024_Measure_A_Count": 120,
        "2024_Measure_B_Ratio": 0.3,
    }
    assert extracted.source_cell_map["2024_Measure_B_Ratio"] == ["F9"]


def test_structure_plan_extractor_recovers_omitted_header_rows_above_vlm_plan(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Bilingual"
    sheet["A1"] = "1-13 continued"
    sheet["A3"] = "单位：个"
    sheet["G3"] = "(unit)"
    sheet["C5"] = "建筑业"
    sheet["D5"] = "批发和"
    sheet["E5"] = "交通运输、"
    sheet["F5"] = "住宿和"
    sheet["G5"] = "信息传输、"
    sheet["D6"] = "零售业"
    sheet["E6"] = "仓储和"
    sheet["F6"] = "餐饮业"
    sheet["G6"] = "软件和信息"
    sheet["E7"] = "邮政业"
    sheet["G7"] = "技术服务业"
    sheet["A8"] = "市    别"
    sheet["B8"] = "City"
    sheet["C8"] = "Construction"
    sheet["D8"] = "Wholesale"
    sheet["E8"] = "Transport,"
    sheet["F8"] = "Hotels"
    sheet["G8"] = "Information"
    sheet["D9"] = "and Retail"
    sheet["E9"] = "Storage"
    sheet["F9"] = "and Catering"
    sheet["G9"] = "Transmission,Software"
    sheet["D10"] = "Trades"
    sheet["E10"] = "and Post"
    sheet["F10"] = "Services"
    sheet["G10"] = "and Information"
    sheet["G11"] = "Technology"
    sheet["A13"] = "全    省"
    sheet["B13"] = "Provincial Total"
    sheet["C13"] = 212719
    sheet["D13"] = 1514268
    sheet["E13"] = 118838
    sheet["F13"] = 93372
    sheet["G13"] = 278974

    path = tmp_path / "bilingual.xlsx"
    workbook.save(path)
    grid = RawCellGridExtractor().extract(str(path))[0]
    plan = TableStructurePlan(
        tableRegion="A5:G13",
        titleRows=[1],
        unitCells=["A3", "G3"],
        headerRows=[8, 9, 10, 11],
        dataStartRow=13,
        dataEndRow=13,
        rowHeaderColumns=["A", "B"],
        valueColumns=["C", "D", "E", "F", "G"],
        categoryRows=[],
        orientation="wide_table",
        confidence=0.86,
        source="vlm",
    )

    extracted = StructurePlanExtractor().extract(grid, plan)

    assert list(extracted.dataframe.columns) == [
        "市别",
        "City",
        "建筑业_Construction",
        "批发和_零售业_Wholesale_and_Retail_Trades",
        "交通运输_仓储和_邮政业_Transport_Storage_and_Post",
        "住宿和_餐饮业_Hotels_and_Catering_Services",
        "信息传输_软件和信息_技术服务业_Information_Transmission_Software_and_Information_Technology",
    ]
