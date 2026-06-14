from app.repositories.table_catalog_repository import TableCatalogRepository


def test_table_catalog_ranks_row_label_matches_without_domain_keywords(
    temp_workspace,
    reset_settings_cache,
) -> None:
    repository = TableCatalogRepository()
    repository.replace_for_file(
        "file_1",
        [
            {
                "file_id": "file_1",
                "sheet_id": "sheet_1",
                "table_alias": "file_1_sheet_1",
                "table_name": "sheet_1",
                "title": "第一张表",
                "source_text": "某地区 2022 资料集",
                "column_text": "项目 单位 2000 2005 2010",
                "row_text": "甲类项目 乙类项目 丙类项目",
            },
            {
                "file_id": "file_1",
                "sheet_id": "sheet_2",
                "table_alias": "file_1_sheet_2",
                "table_name": "sheet_2",
                "title": "第二张表",
                "source_text": "某地区 2022 资料集",
                "column_text": "项目 单位 2000 2005 2010",
                "row_text": "丁类项目 戊类项目 己类项目",
            },
        ],
    )

    matches = repository.search("某地区2000年戊类项目是多少", limit=10)

    assert [match["sheet_id"] for match in matches] == ["sheet_2", "sheet_1"]
    assert matches[0]["score"] > matches[1]["score"]
