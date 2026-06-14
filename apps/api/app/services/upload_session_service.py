from datetime import UTC, datetime
from hashlib import sha256
from math import ceil
from pathlib import Path
from threading import Lock
from uuid import uuid4

from fastapi import HTTPException

from app.core.config import get_settings
from app.repositories.collection_repository import CollectionRepository
from app.repositories.file_repository import FileRepository
from app.repositories.upload_session_repository import UploadSessionRepository
from app.schemas.files import FileResponse
from app.schemas.upload_sessions import UploadSessionResponse
from app.services.file_service import ALLOWED_FILE_EXTENSIONS, FileService, SUPPORTED_FILE_TYPES_TEXT


class UploadSessionService:
    _locks_guard = Lock()
    _locks: dict[str, Lock] = {}

    def __init__(self) -> None:
        self.settings = get_settings()
        self.repository = UploadSessionRepository()
        self.file_repository = FileRepository()
        self.collection_repository = CollectionRepository()
        self.workspace_dir = Path(self.settings.workspace_dir)
        self.uploads_dir = self.workspace_dir / "uploads"
        self.files_dir = self.workspace_dir / "files"
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)

    def create_session(
        self,
        *,
        file_name: str,
        file_size: int,
        chunk_size: int,
        collection_id: str | None,
    ) -> UploadSessionResponse:
        extension = Path(file_name).suffix.lower()
        if extension not in ALLOWED_FILE_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"只支持 {SUPPORTED_FILE_TYPES_TEXT} 文件")
        if collection_id:
            try:
                self.collection_repository.get_collection(collection_id)
            except FileNotFoundError as exc:
                raise HTTPException(status_code=404, detail="资料文件夹不存在") from exc

        now = datetime.now(UTC).isoformat()
        session = self.repository.create(
            {
                "id": uuid4().hex,
                "file_name": file_name,
                "file_size": file_size,
                "chunk_size": chunk_size,
                "total_chunks": ceil(file_size / chunk_size),
                "collection_id": collection_id,
                "status": "created",
                "uploaded_chunks": [],
                "uploaded_bytes": 0,
                "created_at": now,
                "updated_at": now,
            }
        )
        (self.uploads_dir / session["id"] / "chunks").mkdir(parents=True, exist_ok=True)
        return self._to_response(session)

    def list_sessions(self) -> list[UploadSessionResponse]:
        return [self._to_response(row) for row in self.repository.list_active()]

    def get_session(self, session_id: str) -> UploadSessionResponse:
        return self._to_response(self.repository.get(session_id))

    def upload_chunk(self, session_id: str, chunk_index: int, data: bytes) -> UploadSessionResponse:
        with self._session_lock(session_id):
            session = self.repository.get(session_id)
            if session["status"] in {"assembling", "importing", "ready", "needs_review", "failed", "canceled"}:
                raise HTTPException(status_code=409, detail="上传会话已结束")
            if chunk_index < 0 or chunk_index >= session["total_chunks"]:
                raise HTTPException(status_code=400, detail="分片序号超出范围")

            expected_size = self._expected_chunk_size(session, chunk_index)
            if len(data) != expected_size:
                raise HTTPException(status_code=400, detail="分片大小不匹配")

            chunk_path = self._chunk_path(session_id, chunk_index)
            chunk_path.parent.mkdir(parents=True, exist_ok=True)
            if not chunk_path.exists() or chunk_path.stat().st_size != expected_size:
                tmp_path = chunk_path.with_name(f"{chunk_path.name}.{uuid4().hex}.tmp")
                try:
                    tmp_path.write_bytes(data)
                    tmp_path.replace(chunk_path)
                finally:
                    if tmp_path.exists():
                        tmp_path.unlink()

            uploaded_chunks = sorted({*session["uploaded_chunks"], chunk_index})
            uploaded_bytes = sum(self._chunk_path(session_id, index).stat().st_size for index in uploaded_chunks)
            updated = self.repository.update(
                session_id,
                status="uploading",
                uploaded_chunks=uploaded_chunks,
                uploaded_bytes=uploaded_bytes,
                updated_at=datetime.now(UTC).isoformat(),
            )
            return self._to_response(updated)

    def complete_session(self, session_id: str, import_inline: bool = True) -> UploadSessionResponse:
        with self._session_lock(session_id):
            session = self.repository.get(session_id)
            if session["status"] in {"ready", "needs_review"}:
                return self._to_response(session)
            if session["status"] in {"assembling", "importing"}:
                return self._to_response(session)
            if session["status"] == "canceled":
                raise HTTPException(status_code=409, detail="上传会话已取消")
            if len(session["uploaded_chunks"]) != session["total_chunks"]:
                raise HTTPException(status_code=400, detail="分片尚未全部上传")

            self.repository.update(
                session_id,
                status="assembling",
                error=None,
                updated_at=datetime.now(UTC).isoformat(),
            )

            file_id = uuid4().hex
            extension = Path(session["file_name"]).suffix.lower()
            stored_path = self.files_dir / f"{file_id}{extension}"
            tmp_path = stored_path.with_name(f"{stored_path.name}.{session_id}.tmp")
            digest = sha256()
            try:
                with tmp_path.open("wb") as output:
                    for index in range(session["total_chunks"]):
                        chunk_path = self._chunk_path(session_id, index)
                        expected_size = self._expected_chunk_size(session, index)
                        if not chunk_path.exists() or chunk_path.stat().st_size != expected_size:
                            raise HTTPException(status_code=409, detail="分片文件尚未写入完成")
                        chunk = chunk_path.read_bytes()
                        if len(chunk) != expected_size:
                            raise HTTPException(status_code=409, detail="分片文件尚未写入完成")
                        digest.update(chunk)
                        output.write(chunk)
                tmp_path.replace(stored_path)

                created_at = datetime.now(UTC).isoformat()
                self.file_repository.create_file(
                    file_id=file_id,
                    name=session["file_name"],
                    path=str(stored_path),
                    file_hash=digest.hexdigest(),
                    status="uploaded",
                    created_at=created_at,
                    collection_id=session["collection_id"],
                )
                self.repository.update(
                    session_id,
                    status="importing",
                    file_id=file_id,
                    updated_at=datetime.now(UTC).isoformat(),
                )
                if not import_inline:
                    return self._to_response(self.repository.get(session_id))
                return self._import_session_file(session_id)
            except Exception as exc:
                if tmp_path.exists():
                    tmp_path.unlink()
                self.repository.update(
                    session_id,
                    status="failed",
                    file_id=file_id,
                    error=str(exc) or "文件导入失败",
                    updated_at=datetime.now(UTC).isoformat(),
                )
                raise

    def import_session_file(self, session_id: str) -> UploadSessionResponse:
        with self._session_lock(session_id):
            return self._import_session_file(session_id)

    def cancel_session(self, session_id: str) -> None:
        self.repository.update(
            session_id,
            status="canceled",
            updated_at=datetime.now(UTC).isoformat(),
        )

    def _expected_chunk_size(self, session: dict, chunk_index: int) -> int:
        if chunk_index == session["total_chunks"] - 1:
            return session["file_size"] - session["chunk_size"] * chunk_index
        return session["chunk_size"]

    def _chunk_path(self, session_id: str, chunk_index: int) -> Path:
        return self.uploads_dir / session_id / "chunks" / f"{chunk_index}.part"

    def _import_session_file(self, session_id: str) -> UploadSessionResponse:
        session = self.repository.get(session_id)
        if session["status"] in {"ready", "needs_review"}:
            return self._to_response(session)
        if session["status"] != "importing" or not session.get("file_id"):
            raise HTTPException(status_code=409, detail="上传会话尚未进入导入阶段")

        file_id = session["file_id"]
        data_file = self.file_repository.get_file(file_id)
        try:
            FileService().import_to_duckdb(file_id, data_file["path"])
            data_file = self.file_repository.get_file(file_id)
            updated = self.repository.update(
                session_id,
                status=data_file["status"],
                file_id=file_id,
                uploaded_bytes=session["file_size"],
                error=None,
                updated_at=datetime.now(UTC).isoformat(),
            )
            return self._to_response(updated)
        except Exception as exc:
            self.repository.update(
                session_id,
                status="failed",
                file_id=file_id,
                error=str(exc) or "文件导入失败",
                updated_at=datetime.now(UTC).isoformat(),
            )
            raise

    @classmethod
    def _session_lock(cls, session_id: str) -> Lock:
        with cls._locks_guard:
            lock = cls._locks.get(session_id)
            if lock is None:
                lock = Lock()
                cls._locks[session_id] = lock
            return lock

    def _to_response(self, row: dict) -> UploadSessionResponse:
        file_response = None
        file_id = row.get("file_id")
        if file_id:
            try:
                file_response = FileResponse(**self.file_repository.get_file(file_id))
            except FileNotFoundError:
                file_response = None
        return UploadSessionResponse(**row, file=file_response)
