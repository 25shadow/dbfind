from app.repositories.file_repository import FileRepository
from app.services.upload_session_service import UploadSessionService


def test_upload_session_tracks_chunks_and_imports_completed_file(
    temp_workspace,
    reset_settings_cache,
) -> None:
    service = UploadSessionService()
    content = b"name,value\nAlpha,12\n"
    chunk_size = 10

    session = service.create_session(
        file_name="resume.csv",
        file_size=len(content),
        chunk_size=chunk_size,
        collection_id=None,
    )

    service.upload_chunk(session.id, 1, content[chunk_size:])
    service.upload_chunk(session.id, 0, content[:chunk_size])

    restored = service.get_session(session.id)
    assert restored.uploaded_chunks == [0, 1]
    assert restored.uploaded_bytes == len(content)
    assert restored.status == "uploading"

    completed = service.complete_session(session.id)

    assert completed.status == "ready"
    assert completed.file is not None
    assert completed.file.name == "resume.csv"
    assert FileRepository().get_file(completed.file.id)["status"] == "ready"


def test_upload_session_complete_is_idempotent_and_keeps_stored_file(
    temp_workspace,
    reset_settings_cache,
) -> None:
    service = UploadSessionService()
    content = b"name,value\nAlpha,12\n"

    session = service.create_session(
        file_name="repeat-complete.csv",
        file_size=len(content),
        chunk_size=len(content),
        collection_id=None,
    )

    service.upload_chunk(session.id, 0, content)
    first = service.complete_session(session.id)
    second = service.complete_session(session.id)

    assert first.status == "ready"
    assert second.status == "ready"
    assert second.file is not None
    stored = FileRepository().get_file(second.file.id)
    assert stored["status"] == "ready"
    with open(stored["path"], "rb") as file:
        assert file.read() == content
