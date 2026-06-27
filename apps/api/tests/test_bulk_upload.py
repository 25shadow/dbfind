from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.collection_repository import CollectionRepository
from app.repositories.file_repository import FileRepository
from app.services.file_service import FileService


def test_bulk_upload_returns_individual_results(
    temp_workspace,
    reset_settings_cache,
    monkeypatch,
) -> None:
    monkeypatch.setattr(FileService, "import_to_duckdb", lambda self, file_id, path: None)
    client = TestClient(create_app())

    response = client.post(
        "/api/files/bulk-upload",
        files=[
            ("files", ("first.csv", b"name,value\nalpha,1\n", "text/csv")),
            ("files", ("second.txt", b"not supported", "text/plain")),
            ("files", ("third.csv", b"name,value\nbeta,2\n", "text/csv")),
        ],
    )

    assert response.status_code == 200
    assert response.json()["summary"] == {"total": 3, "success": 2, "failed": 1}
    assert [
        (item["fileName"], item["success"], item.get("error"))
        for item in response.json()["results"]
    ] == [
        ("first.csv", True, None),
        ("second.txt", False, "只支持 .xlsx、.xls、.xlsm、.xlsb、.et、.ods 和 .csv 文件"),
        ("third.csv", True, None),
    ]


def test_bulk_upload_accepts_collection_id_on_single_endpoint(
    temp_workspace,
    reset_settings_cache,
    monkeypatch,
) -> None:
    monkeypatch.setattr(FileService, "import_to_duckdb", lambda self, file_id, path: None)
    CollectionRepository().create_collection(
        collection_id="collection_1",
        name="资料文件夹",
        parent_id=None,
        created_at="2026-06-13T00:00:00+00:00",
        updated_at="2026-06-13T00:00:00+00:00",
    )
    client = TestClient(create_app())

    response = client.post(
        "/api/files/bulk-upload",
        data={"collectionId": "collection_1"},
        files=[("files", ("first.csv", b"name,value\nalpha,1\n", "text/csv"))],
    )

    assert response.status_code == 200
    assert response.json()["summary"] == {"total": 1, "success": 1, "failed": 0}
    stored_file = FileRepository().list_files()[0]
    assert stored_file["collection_id"] == "collection_1"
