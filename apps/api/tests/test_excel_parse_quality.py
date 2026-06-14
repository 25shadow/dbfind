import pandas as pd

from app.services.excel_parse_quality import ExcelParseQualityEvaluator


def test_parse_quality_rejects_unit_only_preview_rows():
    dataframe = pd.DataFrame(
        [
            {
                "2023_measure_a": "Label",
                "2023_measure_b": "Description",
            }
        ]
    )

    quality = ExcelParseQualityEvaluator().evaluate(dataframe)

    assert quality.confidence == "low"
    assert "only_one_non_numeric_row" in quality.issues


def test_parse_quality_rejects_repeated_title_like_columns():
    dataframe = pd.DataFrame(
        [
            {
                "title": None,
                "title_2": None,
                "title_3": "指数",
                "title_4": None,
                "item": "平均增长速度",
            },
            {
                "title": None,
                "title_2": None,
                "title_3": 1978,
                "title_4": 1990,
                "item": None,
            },
        ]
    )

    quality = ExcelParseQualityEvaluator().evaluate(dataframe)

    assert quality.confidence == "low"
    assert "repeated_title_like_columns" in quality.issues


def test_parse_quality_accepts_small_numeric_data_table():
    dataframe = pd.DataFrame(
        [
            {
                "group": "Alpha",
                "label": "Alpha label",
                "2023_measure_a": 4708726,
                "2024_measure_a": 4989249,
            },
            {
                "group": "Beta",
                "label": "Beta label",
                "2023_measure_a": 50698,
                "2024_measure_a": 53545,
            },
        ]
    )

    quality = ExcelParseQualityEvaluator().evaluate(dataframe)

    assert quality.confidence == "medium"
    assert quality.is_importable is True
