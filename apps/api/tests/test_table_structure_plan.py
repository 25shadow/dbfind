from app.schemas.table_structure import TableStructurePlan


def test_table_structure_plan_accepts_coordinate_based_structure():
    plan = TableStructurePlan(
        tableRegion="A5:F36",
        titleRows=[1, 2],
        unitCells=["A4", "F4"],
        headerRows=[5, 6, 7, 8],
        dataStartRow=10,
        dataEndRow=36,
        rowHeaderColumns=["A", "B"],
        valueColumns=["C", "D", "E", "F"],
        categoryRows=[],
        orientation="wide_table",
        confidence=0.91,
        source="vlm",
    )

    assert plan.table_region == "A5:F36"
    assert plan.header_rows == [5, 6, 7, 8]
    assert plan.confidence == 0.91
