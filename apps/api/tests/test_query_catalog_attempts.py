from app.adapters.ai_adapter import AiResponseError, GeneratedSql
from app.schemas.query import QueryRequest
from app.services.query_service import QueryService


class FakeAiAdapter:
    def __init__(self) -> None:
        self.generated_schema_texts = []
        self.repair_calls = []

    def generate_sql(self, question: str, schema_text: str) -> GeneratedSql:
        self.generated_schema_texts.append(schema_text)
        if "schema-size:20" in schema_text:
            return GeneratedSql(
                sql='SELECT "value" FROM "file_1_sheet_20";',
                raw_response='{"sql":"SELECT value FROM file_1_sheet_20"}',
            )
        return GeneratedSql(
            sql='SELECT "value" FROM "file_1_sheet_1";',
            raw_response='{"sql":"SELECT value FROM file_1_sheet_1"}',
        )

    def repair_sql(
        self,
        question: str,
        schema_text: str,
        sql: str,
        error: str,
    ) -> GeneratedSql:
        self.repair_calls.append((schema_text, sql, error))
        return GeneratedSql(sql=sql, raw_response="{}")

    def explain_result(self, question: str, sql: str, preview_rows: list[dict]) -> str:
        return "查询已完成。"


class FailingExplainAiAdapter(FakeAiAdapter):
    def explain_result(self, question: str, sql: str, preview_rows: list[dict]) -> str:
        raise AiResponseError("AI 服务返回格式异常：choices 为空。")


class FakeCatalogRepository:
    def __init__(self, matches: list[dict]) -> None:
        self.matches = matches

    def search(self, question: str, limit: int) -> list[dict]:
        return self.matches[:limit]


class FakeSchemaService:
    def __init__(self, matches: list[dict]) -> None:
        self.table_catalog_repository = FakeCatalogRepository(matches)

    def build_schema_text_for_catalog_entries(self, entries: list[dict]) -> str:
        return f"schema-size:{len(entries)}"

    def build_all_files_schema_text(self) -> str:
        return "schema-size:all"


def test_all_files_query_expands_catalog_candidates_before_recording_empty_result(
    temp_workspace,
    reset_settings_cache,
) -> None:
    service = QueryService()
    matches = [
        {
            "file_id": "file_1",
            "sheet_id": f"sheet_{index}",
            "table_alias": f"file_1_sheet_{index}",
        }
        for index in range(1, 21)
    ]
    mappings = [
        {
            "database_alias": "dbfind_file_1",
            "database_path": "file_1.duckdb",
            "file_id": "file_1",
            "sheet_id": f"sheet_{index}",
            "source_table": f"sheet_{index}",
            "table_alias": f"file_1_sheet_{index}",
        }
        for index in range(1, 21)
    ]
    ai_adapter = FakeAiAdapter()
    executed_sql = []

    service.schema_service = FakeSchemaService(matches)
    service.ai_adapter = ai_adapter
    service._all_files_table_mappings = lambda: mappings
    service._sources_for_file = lambda file_id: [
        {
            "fileId": file_id,
            "sheetId": f"sheet_{index}",
            "sheetName": f"sheet_{index}",
            "sheetTitle": f"第 {index} 张表",
            "tableName": f"sheet_{index}",
        }
        for index in range(1, 21)
    ]

    def fake_execute_sql(scope, database_path, table_mappings, sql):
        executed_sql.append(sql)
        if '"file_1_sheet_20"' in sql:
            return [{"value": 20}]
        return []

    service._execute_sql = fake_execute_sql

    response = service.run(QueryRequest(question="查询戊类项目", scope="all"))

    assert response.rows == [{"value": 20}]
    assert response.sql == 'SELECT "value" FROM "file_1_sheet_20";'
    assert response.sources == [
        {
            "fileId": "file_1",
            "sheetId": "sheet_20",
            "sheetName": "sheet_20",
            "sheetTitle": "第 20 张表",
            "tableName": "sheet_20",
        }
    ]
    assert ai_adapter.generated_schema_texts == ["schema-size:8", "schema-size:20"]
    assert ai_adapter.repair_calls == []
    assert executed_sql == [
        'SELECT "value" FROM "file_1_sheet_1";',
        'SELECT "value" FROM "file_1_sheet_20";',
    ]


def test_catalog_attempts_preserve_catalog_alias_for_matching_sheet(
    temp_workspace,
    reset_settings_cache,
) -> None:
    service = QueryService()
    matches = [
        {
            "file_id": "target_file",
            "sheet_id": "target_sheet",
            "table_alias": "file_3_sheet1",
        }
    ]
    mappings = [
        {
            "database_alias": "dbfind_file_1",
            "database_path": "target.duckdb",
            "file_id": "target_file",
            "sheet_id": "target_sheet",
            "source_table": "sheet1",
            "table_alias": "file_1_sheet1",
        },
        {
            "database_alias": "dbfind_file_3",
            "database_path": "other.duckdb",
            "file_id": "other_file",
            "sheet_id": "other_sheet",
            "source_table": "sheet1",
            "table_alias": "file_3_sheet1",
        },
    ]

    service.schema_service = FakeSchemaService(matches)
    attempts = service._all_files_schema_attempts(matches, mappings)

    assert attempts[0][1] == [
        {
            "database_alias": "dbfind_file_1",
            "database_path": "target.duckdb",
            "file_id": "target_file",
            "sheet_id": "target_sheet",
            "source_table": "sheet1",
            "table_alias": "file_3_sheet1",
        }
    ]


def test_execution_mappings_override_stale_aliases_for_sources(
    temp_workspace,
    reset_settings_cache,
) -> None:
    service = QueryService()
    all_mappings = [
        {
            "database_alias": "dbfind_file_3",
            "database_path": "other.duckdb",
            "file_id": "other_file",
            "sheet_id": "other_sheet",
            "source_table": "sheet1",
            "table_alias": "file_3_sheet1",
        }
    ]
    execution_mappings = [
        {
            "database_alias": "dbfind_file_1",
            "database_path": "target.duckdb",
            "file_id": "target_file",
            "sheet_id": "target_sheet",
            "source_table": "sheet1",
            "table_alias": "file_3_sheet1",
        }
    ]

    merged = service._merge_execution_table_mappings(all_mappings, execution_mappings)

    assert merged == execution_mappings


def test_all_files_query_returns_rows_when_explanation_ai_fails(
    temp_workspace,
    reset_settings_cache,
) -> None:
    service = QueryService()
    matches = [
        {
            "file_id": "file_1",
            "sheet_id": "sheet_1",
            "table_alias": "file_1_sheet_1",
        }
    ]
    mappings = [
        {
            "database_alias": "dbfind_file_1",
            "database_path": "file_1.duckdb",
            "file_id": "file_1",
            "sheet_id": "sheet_1",
            "source_table": "sheet_1",
            "table_alias": "file_1_sheet_1",
        }
    ]

    service.schema_service = FakeSchemaService(matches)
    service.ai_adapter = FailingExplainAiAdapter()
    service._all_files_table_mappings = lambda: mappings
    service._execute_sql = lambda scope, database_path, table_mappings, sql: [{"value": 1}]
    service._sources_for_file = lambda file_id: []

    response = service.run(QueryRequest(question="查询指标", scope="all"))

    assert response.rows == [{"value": 1}]
    assert response.explanation == "查询已完成，结果解释暂不可用。"
