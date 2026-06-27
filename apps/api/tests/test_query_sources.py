from app.repositories.query_repository import QueryRepository
from app.services.query_service import QueryService


def test_query_response_returns_stored_source_chain(temp_workspace, reset_settings_cache) -> None:
    sources = [
        {
            "collectionId": "collection_1",
            "collectionName": "广东省2022年农村统计年鉴",
            "fileId": "file_1",
            "fileName": "download.xls",
            "sheetId": "file_1_1",
            "sheetName": "1-2",
            "sheetTitle": "农业主要指标",
        }
    ]
    QueryRepository().create_query(
        query_id="query_1",
        file_id="file_1",
        scope="selected",
        question="广东省2021年乡村户数多少",
        sql='SELECT "乡村户数" FROM "sheet_1";',
        initial_sql='SELECT "乡村户数" FROM "sheet_1";',
        repair_error=None,
        repaired_sql=None,
        was_repaired=False,
        columns=["乡村户数"],
        rows=[{"乡村户数": 1835.5}],
        explanation="查询已完成。",
        sources=sources,
        raw_response="{}",
        created_at="2026-06-12T00:00:00+00:00",
    )

    response = QueryService().get("query_1")

    assert response.sources == sources


def test_sources_for_sql_only_returns_tables_used_by_final_sql(
    temp_workspace,
    reset_settings_cache,
) -> None:
    service = QueryService()
    service.file_repository.repository = None

    def fake_sources_for_file(file_id: str) -> list[dict]:
        return [
            {
                "fileId": file_id,
                "sheetId": f"{file_id}_1",
                "sheetName": "1-1",
                "sheetTitle": "全省主要指标",
                "tableName": "sheet_1",
            },
            {
                "fileId": file_id,
                "sheetId": f"{file_id}_2",
                "sheetName": "1-2",
                "sheetTitle": "农业主要指标",
                "tableName": "sheet_2",
            },
        ]

    service._sources_for_file = fake_sources_for_file
    mappings = [
        {
            "table_alias": "file_1_sheet_1",
            "source_table": "sheet_1",
            "file_id": "file_1",
            "sheet_id": "file_1_1",
        },
        {
            "table_alias": "file_1_sheet_2",
            "source_table": "sheet_2",
            "file_id": "file_1",
            "sheet_id": "file_1_2",
        },
    ]

    sources = service._sources_for_sql(
        scope="all",
        file_id=None,
        sql='SELECT "经济作物" FROM "file_1_sheet_2";',
        table_mappings=mappings,
    )

    assert sources == [
        {
            "fileId": "file_1",
            "sheetId": "file_1_2",
            "sheetName": "1-2",
            "sheetTitle": "农业主要指标",
            "tableName": "sheet_2",
        }
    ]
