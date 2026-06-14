from app.repositories.collection_repository import CollectionRepository
from app.repositories.column_repository import ColumnRepository
from app.repositories.file_repository import FileRepository
from app.repositories.sheet_repository import SheetRepository
from app.services.schema_service import SchemaService


def test_schema_text_includes_collection_context(temp_workspace, reset_settings_cache) -> None:
    CollectionRepository().create_collection(
        collection_id="collection_1",
        name="广东省2022年农村统计年鉴",
        source_region="广东省",
        source_year=2022,
        source_type="农村统计年鉴",
        source_scope="province",
        created_at="2026-06-12T00:00:00+00:00",
        updated_at="2026-06-12T00:00:00+00:00",
    )
    FileRepository().create_file(
        file_id="file_1",
        name="download.xls",
        path="download.xls",
        file_hash="abc",
        status="ready",
        created_at="2026-06-12T00:00:00+00:00",
        collection_id="collection_1",
    )
    SheetRepository().replace_sheets(
        "file_1",
        [
            {
                "id": "sheet_1",
                "name": "1-2",
                "table_name": "sheet_1",
                "row_count": 10,
                "column_count": 1,
                "title": "农业主要指标",
                "subtitle": None,
                "unit": None,
            }
        ],
    )
    ColumnRepository().replace_columns(
        "sheet_1",
        [
            {
                "id": "column_1",
                "name": "乡村户数",
                "normalized_name": "乡村户数",
                "type": "DOUBLE",
                "alias": None,
                "sample_values": [1835.5],
            }
        ],
    )

    schema_text = SchemaService().build_schema_text("file_1")

    assert '-- collection: "广东省2022年农村统计年鉴"' in schema_text
    assert '-- source_region: "广东省"' in schema_text
    assert "-- source_year: 2022" in schema_text
    assert '-- source_type: "农村统计年鉴"' in schema_text
