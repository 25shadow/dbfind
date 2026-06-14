from app.repositories.collection_repository import CollectionRepository
from app.repositories.file_repository import FileRepository


def test_creates_updates_and_lists_collections(temp_workspace, reset_settings_cache) -> None:
    repository = CollectionRepository()

    created = repository.create_collection(
        collection_id="collection_1",
        name="广东省2022年农村统计年鉴",
        source_region="广东省",
        source_year=2022,
        source_type="农村统计年鉴",
        source_scope="province",
        parent_id=None,
        created_at="2026-06-12T00:00:00+00:00",
        updated_at="2026-06-12T00:00:00+00:00",
    )
    updated = repository.update_collection(
        "collection_1",
        name="广东省2023年农村统计年鉴",
        source_region="广东省",
        source_year=2023,
        source_type="农村统计年鉴",
        source_scope="province",
        parent_id=None,
        updated_at="2026-06-12T01:00:00+00:00",
    )

    assert created["name"] == "广东省2022年农村统计年鉴"
    assert updated["source_year"] == 2023
    assert repository.list_collections()[0]["name"] == "广东省2023年农村统计年鉴"


def test_counts_files_in_collection(temp_workspace, reset_settings_cache) -> None:
    collection_repository = CollectionRepository()
    file_repository = FileRepository()
    collection_repository.create_collection(
        collection_id="collection_1",
        name="广东省2022年农村统计年鉴",
        source_region="广东省",
        source_year=2022,
        source_type="农村统计年鉴",
        source_scope="province",
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
        source_region="广东省",
        source_year=None,
        source_type=None,
        source_scope="province",
        parent_id=None,
        created_at="2026-06-12T00:00:00+00:00",
        updated_at="2026-06-12T00:00:00+00:00",
    )
    collection_repository.create_collection(
        collection_id="child",
        name="2022",
        source_region=None,
        source_year=2022,
        source_type=None,
        source_scope=None,
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
        source_region="广东省",
        source_year=None,
        source_type=None,
        source_scope="province",
        parent_id=None,
        created_at="2026-06-12T00:00:00+00:00",
        updated_at="2026-06-12T00:00:00+00:00",
    )
    repository.create_collection(
        collection_id="child",
        name="2022",
        source_region=None,
        source_year=2022,
        source_type=None,
        source_scope=None,
        parent_id="root",
        created_at="2026-06-12T00:01:00+00:00",
        updated_at="2026-06-12T00:01:00+00:00",
    )
    repository.create_collection(
        collection_id="target",
        name="已整理",
        source_region=None,
        source_year=None,
        source_type=None,
        source_scope=None,
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
            source_region=None,
            source_year=None,
            source_type=None,
            source_scope=None,
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
