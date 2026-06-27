from app.repositories.collection_repository import CollectionRepository
from app.repositories.file_repository import FileRepository
import sqlite3


def test_creates_updates_and_lists_collections(temp_workspace, reset_settings_cache) -> None:
    repository = CollectionRepository()

    created = repository.create_collection(
        collection_id="collection_1",
        name="广东省2022年农村统计年鉴",
        parent_id=None,
        created_at="2026-06-12T00:00:00+00:00",
        updated_at="2026-06-12T00:00:00+00:00",
    )
    updated = repository.update_collection(
        "collection_1",
        name="广东省2023年农村统计年鉴",
        parent_id=None,
        updated_at="2026-06-12T01:00:00+00:00",
    )

    assert created["name"] == "广东省2022年农村统计年鉴"
    assert "source_year" not in updated
    assert repository.list_collections()[0]["name"] == "广东省2023年农村统计年鉴"


def test_stores_explicit_tags_and_metadata(temp_workspace, reset_settings_cache) -> None:
    repository = CollectionRepository()

    created = repository.create_collection(
        collection_id="collection_1",
        name="资料集",
        tags=["财务", "已审核"],
        metadata={"owner": "数据组", "period": "Q1"},
        parent_id=None,
        created_at="2026-06-12T00:00:00+00:00",
        updated_at="2026-06-12T00:00:00+00:00",
    )

    assert created["tags"] == ["财务", "已审核"]
    assert created["metadata"] == {"owner": "数据组", "period": "Q1"}


def test_init_removes_legacy_source_columns(temp_workspace, reset_settings_cache) -> None:
    db_path = temp_workspace / "meta.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE collections (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                source_region TEXT,
                source_year INTEGER,
                source_type TEXT,
                source_scope TEXT,
                parent_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO collections (
                id, name, source_region, source_year, source_type,
                source_scope, parent_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "collection_1",
                "旧资料",
                "广东省",
                2022,
                "统计年鉴",
                "province",
                None,
                "2026-06-12T00:00:00+00:00",
                "2026-06-12T00:00:00+00:00",
            ),
        )

    repository = CollectionRepository()
    columns = {row["name"] for row in repository._connect().execute("PRAGMA table_info(collections)").fetchall()}

    assert {"source_region", "source_year", "source_type", "source_scope"}.isdisjoint(columns)
    assert {"tags", "metadata"}.issubset(columns)
    assert repository.get_collection("collection_1")["name"] == "旧资料"


def test_counts_files_in_collection(temp_workspace, reset_settings_cache) -> None:
    collection_repository = CollectionRepository()
    file_repository = FileRepository()
    collection_repository.create_collection(
        collection_id="collection_1",
        name="广东省2022年农村统计年鉴",
        parent_id=None,
        created_at="2026-06-12T00:00:00+00:00",
        updated_at="2026-06-12T00:00:00+00:00",
    )
    file_repository.create_file(
        file_id="file_1",
        name="download.xls",
        path="download.xls",
        file_hash="abc",
        status="ready",
        created_at="2026-06-12T00:00:00+00:00",
        collection_id="collection_1",
    )

    assert collection_repository.count_files("collection_1") == 1


def test_counts_files_recursively_through_child_collections(temp_workspace, reset_settings_cache) -> None:
    collection_repository = CollectionRepository()
    file_repository = FileRepository()
    collection_repository.create_collection(
        collection_id="root",
        name="广东省年鉴",
        parent_id=None,
        created_at="2026-06-12T00:00:00+00:00",
        updated_at="2026-06-12T00:00:00+00:00",
    )
    collection_repository.create_collection(
        collection_id="child",
        name="2022",
        parent_id="root",
        created_at="2026-06-12T00:01:00+00:00",
        updated_at="2026-06-12T00:01:00+00:00",
    )
    file_repository.create_file(
        file_id="file_1",
        name="download.xls",
        path="download.xls",
        file_hash="abc",
        status="ready",
        created_at="2026-06-12T00:00:00+00:00",
        collection_id="child",
    )

    assert collection_repository.count_files("root") == 1


def test_lists_child_collections_and_moves_collection(temp_workspace, reset_settings_cache) -> None:
    repository = CollectionRepository()
    repository.create_collection(
        collection_id="root",
        name="广东省年鉴",
        parent_id=None,
        created_at="2026-06-12T00:00:00+00:00",
        updated_at="2026-06-12T00:00:00+00:00",
    )
    repository.create_collection(
        collection_id="child",
        name="2022",
        parent_id="root",
        created_at="2026-06-12T00:01:00+00:00",
        updated_at="2026-06-12T00:01:00+00:00",
    )
    repository.create_collection(
        collection_id="target",
        name="已整理",
        parent_id=None,
        created_at="2026-06-12T00:02:00+00:00",
        updated_at="2026-06-12T00:02:00+00:00",
    )

    assert [item["id"] for item in repository.list_children("root")] == ["child"]

    repository.move_collection("child", "target", "2026-06-12T01:00:00+00:00")

    assert repository.get_collection("child")["parent_id"] == "target"
    assert [item["id"] for item in repository.list_children("target")] == ["child"]


def test_moves_files_between_collections(temp_workspace, reset_settings_cache) -> None:
    collection_repository = CollectionRepository()
    file_repository = FileRepository()
    for collection_id in ["source", "target"]:
        collection_repository.create_collection(
            collection_id=collection_id,
            name=collection_id,
            parent_id=None,
            created_at="2026-06-12T00:00:00+00:00",
            updated_at="2026-06-12T00:00:00+00:00",
        )
    for file_id in ["file_1", "file_2"]:
        file_repository.create_file(
            file_id=file_id,
            name=f"{file_id}.xls",
            path=f"{file_id}.xls",
            file_hash=file_id,
            status="ready",
            created_at="2026-06-12T00:00:00+00:00",
            collection_id="source",
        )

    file_repository.move_files(["file_1", "file_2"], "target")

    assert file_repository.get_file("file_1")["collection_id"] == "target"
    assert file_repository.get_file("file_2")["collection_id"] == "target"
