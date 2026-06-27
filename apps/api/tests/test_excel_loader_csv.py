import pandas as pd
import pytest

from app.services.excel_loader import ExcelLoader


def test_excel_loader_loads_csv_only(tmp_path):
    path = tmp_path / "source.csv"
    path.write_text("城市,金额\n广州,10\n韶关,\n", encoding="utf-8")

    loaded = ExcelLoader().load(str(path))

    assert len(loaded) == 1
    assert loaded[0].name == "source"
    assert loaded[0].dataframe.to_dict(orient="records") == [
        {"城市": "广州", "金额": 10.0},
        {"城市": "韶关", "金额": None},
    ]


def test_excel_loader_rejects_excel_files(tmp_path):
    path = tmp_path / "source.xlsx"
    pd.DataFrame([{"城市": "广州"}]).to_excel(path, index=False)

    with pytest.raises(ValueError, match="Excel 文件请使用结构解析流程"):
        ExcelLoader().load(str(path))
