from fastapi.testclient import TestClient

from app.main import create_app


def test_upload_session_api_resumes_with_uploaded_chunk_indexes(
    temp_workspace,
    reset_settings_cache,
) -> None:
    client = TestClient(create_app())
    content = b"name,value\nAlpha,12\n"

    created = client.post(
        "/api/upload-sessions",
        json={
            "fileName": "api-resume.csv",
            "fileSize": len(content),
            "chunkSize": 10,
        },
    )

    assert created.status_code == 200
    session_id = created.json()["id"]

    chunk_response = client.put(
        f"/api/upload-sessions/{session_id}/chunks/0",
        files={"chunk": ("0.part", content[:10], "application/octet-stream")},
    )

    assert chunk_response.status_code == 200
    assert chunk_response.json()["uploadedChunks"] == [0]

    restored = client.get(f"/api/upload-sessions/{session_id}")
    assert restored.status_code == 200
    assert restored.json()["uploadedChunks"] == [0]

    client.put(
        f"/api/upload-sessions/{session_id}/chunks/1",
        files={"chunk": ("1.part", content[10:], "application/octet-stream")},
    )
    completed = client.post(f"/api/upload-sessions/{session_id}/complete")

    assert completed.status_code == 200
    assert completed.json()["status"] == "importing"
    assert completed.json()["file"]["name"] == "api-resume.csv"

    restored_after_import = client.get(f"/api/upload-sessions/{session_id}")
    assert restored_after_import.status_code == 200
    assert restored_after_import.json()["status"] == "ready"
